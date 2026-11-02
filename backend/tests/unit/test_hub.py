"""Unit tests for the BroadcastHub and WebSocket endpoint."""

import asyncio
import json
import time

from monitor.presentation.ws.hub import BroadcastHub


class TestBroadcastHub:
    """Tests for BroadcastHub class."""

    def test_drop_oldest(self) -> None:
        """Queue should drop oldest when full, with drop counter incremented."""
        hub = BroadcastHub(queue_size=3)
        client_id = "client1"
        ip = "192.168.1.1"

        # Connect client
        result = asyncio.run(hub.connect(client_id, ip, 3))
        assert result is None, "Client should be accepted"

        # Publish 4 messages
        for i in range(4):
            hub.publish(f"message-{i}")

        # Check queue has 3 messages (oldest dropped)
        assert hub.get_queue_size(client_id) == 3
        # Check drop counter
        assert hub.get_client_drops(client_id) == 1

    def test_publish_never_blocks(self) -> None:
        """Publish should be non-blocking and return immediately."""
        hub = BroadcastHub()

        async def publish_loop() -> None:
            for _ in range(100):
                hub.publish("test-message")

        # This should complete quickly without blocking
        start = time.monotonic()
        asyncio.run(publish_loop())
        elapsed = time.monotonic() - start

        # Should complete in well under 1 second (no blocking)
        assert elapsed < 1.0, "publish() should not block"

    def test_disconnect_removes_client(self) -> None:
        """Disconnecting a client should remove it from tracking."""
        hub = BroadcastHub()
        client_id = "client1"
        ip = "192.168.1.1"

        # Connect client
        result = asyncio.run(hub.connect(client_id, ip, 4))
        assert result is None

        # Verify client is tracked
        assert hub.get_total_clients() == 1

        # Disconnect
        hub.disconnect(client_id, "test disconnect")

        # Verify client is removed
        assert hub.get_total_clients() == 0
        assert hub.get_queue_size(client_id) == 0

    def test_max_clients_limit(self) -> None:
        """Should reject connection when max_clients exceeded."""
        hub = BroadcastHub(max_clients=2)

        async def connect_client(client_id: str) -> dict | None:
            return await hub.connect(client_id, f"10.0.0.{client_id}", 4)

        # Connect first client
        result1 = asyncio.run(connect_client("client1"))
        assert result1 is None

        # Connect second client
        result2 = asyncio.run(connect_client("client2"))
        assert result2 is None

        # Try to connect third client - should be rejected
        result3 = asyncio.run(connect_client("client3"))
        assert result3 is not None
        assert result3["code"] == 1013
        assert "max client capacity" in result3["reason"].lower()

    def test_max_clients_per_ip(self) -> None:
        """Should reject connections from same IP that exceeds limit."""
        hub = BroadcastHub(max_clients_per_ip=2)

        async def run_test() -> None:
            # Connect first client from IP 100
            result1 = await hub.connect("client-1", "192.168.1.100", 4)
            assert result1 is None

            # Connect second client from same IP
            result2 = await hub.connect("client-2", "192.168.1.100", 4)
            assert result2 is None

            # Third client from same IP should be rejected
            result3 = await hub.connect("client-3", "192.168.1.100", 4)
            assert result3 is not None
            assert result3["code"] == 1013
            assert "too many clients" in result3["reason"].lower()

        asyncio.run(run_test())

    def test_copy_on_iterate_safety(self) -> None:
        """Modifying client set during iteration should be safe."""
        hub = BroadcastHub()

        async def run_test() -> None:
            # Connect multiple clients
            for i in range(5):
                await hub.connect(f"client{i}", f"10.0.0.{i}", 4)

            # While publishing, simulate one client disconnecting
            for _ in range(10):
                hub.publish("message")
            hub.disconnect("client0", "test")
            for _ in range(10):
                hub.publish("message")

        asyncio.run(run_test())

        # Should have 4 clients left
        assert hub.get_total_clients() == 4

    def test_build_hello_message(self) -> None:
        """Build hello message should be valid JSON."""
        hub = BroadcastHub()
        msg = hub.build_hello_message()
        assert msg is not None
        # Verify it's valid JSON
        parsed = json.loads(msg)
        assert parsed["v"] == 1
        assert parsed["type"] == "hello"
        assert "data" in parsed
        assert "limits" in parsed["data"]

    def test_hello_message_structure(self) -> None:
        """Hello message should have correct structure."""
        hub = BroadcastHub()
        msg = hub.build_hello_message()
        parsed = json.loads(msg)

        # Verify required fields
        assert "v" in parsed
        assert "type" in parsed
        assert "seq" in parsed
        assert "ts" in parsed
        assert "data" in parsed

        # Verify data structure
        data = parsed["data"]
        assert data["type"] == "hello"
        assert "interval_ms" in data
        assert "max_message_bytes" in data
        assert "groups" in data
        assert "server_time" in data
        assert "limits" in data

        # Verify limits structure
        limits = data["limits"]
        assert "max_clients" in limits
        assert "max_clients_per_ip" in limits
        assert "max_message_bytes" in limits
        assert "rate_limit_burst" in limits
        assert "rate_limit_refill_per_second" in limits
        assert "send_timeout_seconds" in limits
        assert "handshake_timeout_seconds" in limits

    def test_hub_returns_correct_error_codes(self) -> None:
        """Hub should return correct close codes for rejection."""
        hub = BroadcastHub(max_clients=1, max_clients_per_ip=1)

        async def test_rejection() -> None:
            # First connection should succeed
            result1 = await hub.connect("client1", "127.0.0.1", 4)
            assert result1 is None

            # Same IP should be rejected with 1013
            result2 = await hub.connect("client2", "127.0.0.1", 4)
            assert result2 is not None
            assert result2["code"] == 1013

        asyncio.run(test_rejection())

    def test_publish_adds_to_client_queues(self) -> None:
        """Publish should add messages to all client queues."""
        hub = BroadcastHub()

        async def test_publish() -> None:
            # Connect clients
            await hub.connect("c1", "127.0.0.1", 4)
            await hub.connect("c2", "127.0.0.2", 4)

            # Publish message
            hub.publish("test-message")

            # Check messages are in queues
            assert hub.get_queue_size("c1") == 1
            assert hub.get_queue_size("c2") == 1

        asyncio.run(test_publish())

    def test_get_next_message_returns_oldest_first(self) -> None:
        """get_next_message should return messages in FIFO order."""
        hub = BroadcastHub(queue_size=5)

        async def test_order() -> None:
            await hub.connect("c1", "127.0.0.1", 5)

            hub.publish("first")
            hub.publish("second")
            hub.publish("third")

            # Should get messages in order
            assert hub.get_next_message("c1") == "first"
            assert hub.get_next_message("c1") == "second"
            assert hub.get_next_message("c1") == "third"

        asyncio.run(test_order())
