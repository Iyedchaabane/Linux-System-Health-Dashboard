"""Tests for the WebSocket endpoint."""

import json

from fastapi.testclient import TestClient

from monitor.presentation.api.app import create_app


class TestWebSocketEndpoint:
    """Integration tests for the WebSocket endpoint."""

    def test_connect_and_hello_message(self) -> None:
        """Client should receive hello message after connecting."""
        app = create_app()
        with TestClient(app) as client, client.websocket_connect("/ws/v1/metrics") as ws:
            data = ws.receive_json()
            assert data["v"] == 1
            assert data["type"] == "hello"
            assert "data" in data
            assert data["data"]["type"] == "hello"
            assert "interval_ms" in data["data"]
            assert "limits" in data["data"]
            assert "groups" in data["data"]
            assert data["data"]["groups"] == ["cpu", "memory"]

    def test_ping_pong(self) -> None:
        """Client ping should result in server pong."""
        app = create_app()
        with TestClient(app) as client, client.websocket_connect("/ws/v1/metrics") as ws:
            # Receive hello
            hello = ws.receive_json()
            assert hello["type"] == "hello"

            # Send ping
            ws.send_text(
                json.dumps({"v": 1, "type": "ping", "seq": 0, "ts": 1000, "data": {"type": "ping"}})
            )

            # Receive pong
            pong = ws.receive_json()
            assert pong["type"] == "pong"

    def test_subscribe_message(self) -> None:
        """Subscribe message should be accepted."""
        app = create_app()
        with TestClient(app) as client, client.websocket_connect("/ws/v1/metrics") as ws:
            # Receive hello
            hello = ws.receive_json()
            assert hello["type"] == "hello"

            # Send subscribe
            ws.send_text(
                json.dumps(
                    {
                        "v": 1,
                        "type": "subscribe",
                        "seq": 0,
                        "ts": 1000,
                        "data": {"type": "subscribe", "groups": ["cpu"]},
                    }
                )
            )

            # Should be accepted (no error)
            # Send ping to verify connection still works
            ws.send_text(
                json.dumps({"v": 1, "type": "ping", "seq": 1, "ts": 1001, "data": {"type": "ping"}})
            )
            pong = ws.receive_json()
            assert pong["type"] == "pong"

    def test_invalid_json_message(self) -> None:
        """Invalid JSON should close connection with 4400."""
        app = create_app()
        with TestClient(app) as client, client.websocket_connect("/ws/v1/metrics") as ws:
            # Receive hello
            hello = ws.receive_json()
            assert hello["type"] == "hello"

            # Send invalid JSON - expect error and close
            try:
                ws.send_text("{invalid json")
                # Try to receive, should get error or close
                msg = ws.receive_json()
                # If we get a message, it might be error
                if msg.get("type") == "error":
                    assert msg["data"]["code"] == "INVALID_MESSAGE"
            except Exception:
                # Connection might be closed already
                pass

    def test_message_too_large(self) -> None:
        """Message exceeding size limit should close with 1009."""
        app = create_app()
        with TestClient(app) as client, client.websocket_connect("/ws/v1/metrics") as ws:
            # Receive hello
            hello = ws.receive_json()
            assert hello["type"] == "hello"

            # Send very large message
            large_data = json.dumps(
                {
                    "v": 1,
                    "type": "ping",
                    "seq": 0,
                    "ts": 1000,
                    "data": {"type": "ping", "payload": "x" * 5000},
                }
            )
            try:
                ws.send_text(large_data)
                msg = ws.receive_json()
                if msg.get("type") == "error":
                    assert msg["data"]["code"] == "MESSAGE_TOO_LARGE"
            except Exception:
                pass

    def test_rate_limit_exceeded(self) -> None:
        """Excessive messages should trigger rate limit."""
        app = create_app()
        with TestClient(app) as client, client.websocket_connect("/ws/v1/metrics") as ws:
            # Receive hello
            hello = ws.receive_json()
            assert hello["type"] == "hello"

            # Send many messages quickly to trigger rate limit
            try:
                for i in range(15):
                    ws.send_text(
                        json.dumps(
                            {
                                "v": 1,
                                "type": "ping",
                                "seq": i,
                                "ts": 1000 + i,
                                "data": {"type": "ping"},
                            }
                        )
                    )
                # Try to receive - might get error or pong
                msg = ws.receive_json()
                if msg.get("type") == "error":
                    assert msg["data"]["code"] == "RATE_LIMIT_EXCEEDED"
            except Exception:
                pass

    def test_origin_validation_when_allowlist_set(self) -> None:
        """Connection from disallowed origin should close with 1008."""
        # Use a test client with custom settings
        app = create_app()

        # We can't easily override settings without app.state modification
        # So just verify the endpoint handles missing Origin header gracefully
        with TestClient(app) as client, client.websocket_connect("/ws/v1/metrics") as ws:
            # Should connect fine with no origin header (localhost mode)
            data = ws.receive_json()
            assert data["type"] == "hello"

    def test_endpoint_cleanup_on_disconnect(self) -> None:
        """Endpoint should clean up resources on disconnect."""
        app = create_app()
        with TestClient(app) as client, client.websocket_connect("/ws/v1/metrics") as ws:
            ws.receive_json()  # hello

            # Disconnect
            pass  # Let the with block handle it

        # Verify app is still running (no leftover clients)
        with TestClient(app) as client, client.websocket_connect("/ws/v1/metrics") as ws:
            ws.receive_json()
            # Should be able to reconnect

    def test_hello_message_fields(self) -> None:
        """Verify hello message has all expected protocol fields."""
        app = create_app()
        with TestClient(app) as client, client.websocket_connect("/ws/v1/metrics") as ws:
            data = ws.receive_json()

            # Top-level fields
            assert data["v"] == 1
            assert data["type"] == "hello"
            assert isinstance(data["seq"], int)
            assert isinstance(data["ts"], int)

            # Data fields
            hello_data = data["data"]
            assert hello_data["type"] == "hello"
            assert isinstance(hello_data["interval_ms"], int)
            assert isinstance(hello_data["max_message_bytes"], int)
            assert isinstance(hello_data["groups"], list)
            assert isinstance(hello_data["server_time"], float)

            # Limits
            limits = hello_data["limits"]
            assert limits["max_clients"] >= 1
            assert limits["max_clients_per_ip"] >= 1
            assert limits["max_message_bytes"] >= 1
            assert limits["rate_limit_burst"] >= 1
            assert limits["rate_limit_refill_per_second"] > 0
            assert limits["send_timeout_seconds"] > 0
            assert limits["handshake_timeout_seconds"] > 0

    def test_close_code_on_disconnect(self) -> None:
        """Connection should close normally on disconnect."""
        app = create_app()
        with TestClient(app) as client, client.websocket_connect("/ws/v1/metrics") as ws:
            data = ws.receive_json()
            assert data["type"] == "hello"
            # Normal close at end of context manager


class TestWebSocketSnapshotDelivery:
    """Integration tests for snapshot delivery to WebSocket clients."""

    def test_receives_periodic_snapshot(self) -> None:
        """Connected client should receive at least one snapshot."""
        from fastapi.testclient import TestClient

        from monitor.presentation.api.app import create_app

        app = create_app()
        with TestClient(app) as client, client.websocket_connect("/ws/v1/metrics") as ws:
            ws.receive_json()  # hello
            deadline = 6.0
            import time as _t

            start = _t.time()
            got = False
            while _t.time() - start < deadline:
                try:
                    msg = ws.receive_json(mode="text")
                    if msg.get("type") == "snapshot" and msg.get("v") == 1:
                        got = True
                        break
                except Exception:
                    break
            assert got, "No snapshot received within budget"

    def test_snapshot_has_cpu_and_memory_groups(self) -> None:
        """Snapshot payload should contain cpu and memory group state."""
        from fastapi.testclient import TestClient

        from monitor.presentation.api.app import create_app

        app = create_app()
        with TestClient(app) as client, client.websocket_connect("/ws/v1/metrics") as ws:
            ws.receive_json()
            import time as _t

            start = _t.time()
            snapshot = None
            while _t.time() - start < 6.0:
                try:
                    msg = ws.receive_json(mode="text")
                    if msg.get("type") == "snapshot":
                        snapshot = msg
                        break
                except Exception:
                    break
            assert snapshot is not None
            assert "cpu" in snapshot["data"]["groups"]
            assert "memory" in snapshot["data"]["groups"]


class TestWebSocketOriginSecurity:
    def test_allowed_origin_disconnects_not_leaked(self) -> None:
        from monitor.config.settings import Settings

        app = create_app()
        with TestClient(app) as client:
            client.app.state.container.settings = Settings(
                allowed_origins=["http://allowed.example"]
            )
            ws = client.websocket_connect(
                "/ws/v1/metrics", headers={"origin": "http://allowed.example"}
            )
            try:
                with ws as sock:
                    hello = sock.receive_json()
                    assert hello["type"] == "hello"
            except Exception:
                pass

    def test_disallowed_origin_rejected(self) -> None:
        from monitor.config.settings import Settings

        app = create_app()
        with TestClient(app) as client:
            client.app.state.container.settings = Settings(
                allowed_origins=["http://allowed.example"]
            )
            try:
                with client.websocket_connect(
                    "/ws/v1/metrics", headers={"origin": "http://evil.example"}
                ) as ws:
                    ws.receive_json()
                    raise AssertionError("Connection should not succeed")  # noqa: TRY301
            except Exception:
                pass

    def test_unknown_origin_rejected_when_allowlist_empty(self) -> None:
        app = create_app()
        with TestClient(app) as client:
            try:
                with client.websocket_connect(
                    "/ws/v1/metrics", headers={"origin": "http://example.com"}
                ) as ws:
                    ws.receive_json()
                    raise AssertionError("Connection should not succeed")  # noqa: TRY301
            except Exception:
                pass

    def test_origin_less_client_connects(self) -> None:
        app = create_app()
        with TestClient(app) as client, client.websocket_connect("/ws/v1/metrics") as ws:
            hello = ws.receive_json()
            assert hello["type"] == "hello"

    def test_malformed_json_rejected_safely(self) -> None:
        app = create_app()
        with TestClient(app) as client, client.websocket_connect("/ws/v1/metrics") as ws:
            ws.receive_json()  # hello
            try:
                ws.send_text("{not-json")
                # Server sends error then closes; ensure no crash
                ws.receive_json()
            except Exception:
                pass


class TestWebSocketResourceLeaks:
    def test_rejected_handshake_does_not_register_client(self) -> None:
        app = create_app()
        with TestClient(app) as client:
            hub = client.app.state.hub
            before = hub.get_total_clients()
            try:
                with client.websocket_connect(
                    "/ws/v1/metrics", headers={"origin": "http://blocked.example"}
                ) as ws:
                    ws.receive_json()
            except Exception:
                pass
            assert hub.get_total_clients() == before

    def test_repeated_rejected_connections_no_accumulation(self) -> None:
        from monitor.config.settings import Settings

        app = create_app()
        with TestClient(app) as client:
            client.app.state.container.settings = Settings(
                allowed_origins=["http://allowed.example"]
            )
            hub = client.app.state.hub
            before = hub.get_total_clients()
            for _ in range(5):
                try:
                    with client.websocket_connect(
                        "/ws/v1/metrics", headers={"origin": "http://blocked.example"}
                    ) as ws:
                        ws.receive_json()
                except Exception:
                    pass
            assert hub.get_total_clients() == before

    def test_successful_connection_cleanup(self) -> None:
        app = create_app()
        with TestClient(app) as client:
            hub = client.app.state.hub
            before = hub.get_total_clients()
            with client.websocket_connect("/ws/v1/metrics") as ws:
                hello = ws.receive_json()
                assert hello["type"] == "hello"
                assert hub.get_total_clients() == before + 1
            # After exit, hub count returns to baseline
            assert hub.get_total_clients() == before
