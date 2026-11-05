"""Regression tests for connection ownership and outbound accounting."""

import asyncio
import json
from unittest.mock import Mock

import pytest

from monitor.presentation.ws.endpoint import _OutboundMessages, metrics_ws
from monitor.presentation.ws.hub import BroadcastHub
from tests.fakes.ws_transport import WsTransport


def snapshot(number: int) -> str:
    return json.dumps(
        {
            "v": 1,
            "type": "snapshot",
            "seq": 900,
            "ts": number,
            "data": {"type": "snapshot", "groups": {}, "meta": {"dropped_since_last": 0}},
        }
    )


def messages(transport: WsTransport) -> list[dict]:
    return [json.loads(m["text"]) for m in transport.sent if m["type"] == "websocket.send"]


@pytest.mark.parametrize(
    "failure", ["accept", "hello_timeout", "hello_error", "sender", "sender_timeout"]
)
async def test_failure_releases_registration_and_tasks(
    failure: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = BroadcastHub()
    transport = WsTransport(hub)
    disconnect = Mock(wraps=hub.disconnect)
    hub.disconnect = disconnect
    before = asyncio.all_tasks()
    send_text = transport.socket.send_text

    async def timed_send(raw: str) -> None:
        kind = json.loads(raw)["type"]
        if (failure == "hello_timeout" and kind == "hello") or (
            failure == "sender_timeout" and kind == "snapshot"
        ):
            # Inject the deadline result outside Starlette's OSError translation.
            raise TimeoutError
        await send_text(raw)

    monkeypatch.setattr(transport.socket, "send_text", timed_send)

    async def send(message: dict) -> None:
        if message["type"] == "websocket.accept" and failure == "accept":
            raise RuntimeError("accept failed")
        if message["type"] != "websocket.send":
            return
        kind = json.loads(message["text"])["type"]
        if kind == "hello":
            if failure == "hello_error":
                raise RuntimeError("hello failed")
            hub.publish(snapshot(1))
        if kind == "snapshot":
            raise RuntimeError("sender failed")

    transport.on_send = send
    await metrics_ws(transport.socket)
    assert hub.get_total_clients() == 0
    assert hub.get_clients_per_ip("127.0.0.1") == 0
    disconnect.assert_called_once()
    assert asyncio.all_tasks() == before
    if failure != "accept":
        assert transport.sent[-1]["code"] == (1013 if "timeout" in failure else 1011)


async def test_cancellation_during_hello_releases_registration() -> None:
    hub = BroadcastHub()
    transport = WsTransport(hub)
    sending = asyncio.Event()
    cancelled = asyncio.Event()
    before = asyncio.all_tasks()

    async def send(message: dict) -> None:
        if message["type"] == "websocket.send":
            sending.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    transport.on_send = send
    task = asyncio.create_task(metrics_ws(transport.socket))
    await sending.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()
    assert hub.get_total_clients() == hub.get_clients_per_ip("127.0.0.1") == 0
    assert asyncio.all_tasks() == before


async def test_disconnect_cancels_inflight_sender() -> None:
    hub = BroadcastHub()
    transport = WsTransport(hub)
    cancelled = asyncio.Event()
    before = asyncio.all_tasks()

    async def send(message: dict) -> None:
        if message["type"] != "websocket.send":
            return
        if json.loads(message["text"])["type"] == "hello":
            hub.publish(snapshot(1))
        else:
            transport.incoming.put_nowait({"type": "websocket.disconnect", "code": 1000})
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    transport.on_send = send
    await metrics_ws(transport.socket)
    assert cancelled.is_set()
    assert hub.get_total_clients() == hub.get_clients_per_ip("127.0.0.1") == 0
    assert asyncio.all_tasks() == before


async def test_endpoint_mixed_snapshot_pong_and_error_sequence() -> None:
    hub = BroadcastHub()
    transport = WsTransport(hub)

    async def send(message: dict) -> None:
        if message["type"] != "websocket.send":
            return
        kind = json.loads(message["text"])["type"]
        if kind == "hello":
            hub.publish(snapshot(1))
        elif kind == "snapshot":
            transport.incoming.put_nowait({"type": "websocket.receive", "text": '{"type":"ping"}'})
        elif kind == "pong":
            transport.incoming.put_nowait({"type": "websocket.receive", "text": "{"})

    transport.on_send = send
    await metrics_ws(transport.socket)
    assert [(m["type"], m["seq"]) for m in messages(transport)] == [
        ("hello", 0),
        ("snapshot", 1),
        ("pong", 2),
        ("error", 3),
    ]
    assert hub.get_total_clients() == hub.get_clients_per_ip("127.0.0.1") == 0


async def test_overflow_fifo_and_delivered_drop_metadata() -> None:
    hub = BroadcastHub(queue_size=2)
    transport = WsTransport(hub)

    async def send(message: dict) -> None:
        if message["type"] != "websocket.send":
            return
        data = json.loads(message["text"])
        if data["type"] == "hello":
            for number in range(4):
                hub.publish(snapshot(number))
        elif data["type"] == "snapshot" and data["ts"] == 3:
            transport.incoming.put_nowait({"type": "websocket.disconnect", "code": 1000})

    transport.on_send = send
    await metrics_ws(transport.socket)
    delivered = messages(transport)
    assert [m["seq"] for m in delivered] == [0, 3, 4]
    assert [m["ts"] for m in delivered[1:]] == [2, 3]
    assert [m["data"]["meta"]["dropped_since_last"] for m in delivered[1:]] == [2, 0]
    assert hub.get_total_clients() == hub.get_clients_per_ip("127.0.0.1") == 0


async def test_drops_during_send_survive_until_next_successful_snapshot() -> None:
    hub = BroadcastHub(queue_size=1)
    await hub.connect("client", "127.0.0.1", 1)
    transport = WsTransport(hub)
    await transport.socket.accept()
    outbound = _OutboundMessages(transport.socket, hub, "client", 5)
    await outbound.send(hub.build_hello_message())
    hub.publish(snapshot(1))
    hub.publish(snapshot(2))

    async def send(message: dict) -> None:
        if message["type"] == "websocket.send":
            hub.publish(snapshot(3))
            hub.publish(snapshot(4))

    transport.on_send = send
    first = hub.get_next_message("client")
    assert first is not None
    await outbound.send(first)
    transport.on_send = None
    second = hub.get_next_message("client")
    assert second is not None
    await outbound.send(second)
    await outbound.send(snapshot(5))
    delivered = messages(transport)[1:]
    assert [m["seq"] for m in delivered] == [2, 4, 5]
    assert [m["data"]["meta"]["dropped_since_last"] for m in delivered] == [1, 1, 0]


async def test_failed_snapshot_does_not_acknowledge_drops() -> None:
    hub = BroadcastHub(queue_size=1)
    await hub.connect("client", "127.0.0.1", 1)
    transport = WsTransport(hub)
    await transport.socket.accept()
    outbound = _OutboundMessages(transport.socket, hub, "client", 5)
    await outbound.send(hub.build_hello_message())
    hub.publish(snapshot(1))
    hub.publish(snapshot(2))

    async def fail(message: dict) -> None:
        raise RuntimeError("send failed")

    transport.on_send = fail
    with pytest.raises(RuntimeError, match="send failed"):
        await outbound.send(snapshot(3))
    transport.on_send = None
    await outbound.send(snapshot(4))
    assert messages(transport)[-1]["data"]["meta"]["dropped_since_last"] == 1
    assert messages(transport)[-1]["seq"] == 3


async def test_concurrent_writes_are_serialized() -> None:
    hub = BroadcastHub()
    await hub.connect("client", "127.0.0.1", 4)
    transport = WsTransport(hub)
    await transport.socket.accept()
    outbound = _OutboundMessages(transport.socket, hub, "client", 5)
    await outbound.send(hub.build_hello_message())
    sending = asyncio.Event()
    release = asyncio.Event()
    pong_attempted = asyncio.Event()

    async def block_snapshot(message: dict) -> None:
        if json.loads(message["text"])["type"] == "snapshot":
            sending.set()
            await release.wait()

    async def pong() -> None:
        pong_attempted.set()
        await outbound.send('{"type":"pong","seq":0,"data":{}}')

    transport.on_send = block_snapshot
    first = asyncio.create_task(outbound.send(snapshot(1)))
    await sending.wait()
    second = asyncio.create_task(pong())
    await pong_attempted.wait()
    assert [m["type"] for m in messages(transport)] == ["hello"]
    release.set()
    await asyncio.gather(first, second)
    assert [(m["type"], m["seq"]) for m in messages(transport)] == [
        ("hello", 0),
        ("snapshot", 1),
        ("pong", 2),
    ]


async def test_clients_have_independent_sequences_and_drop_reports() -> None:
    hub = BroadcastHub(queue_size=1)
    slow = WsTransport(hub)
    fast = WsTransport(hub)
    outputs = []
    for name, transport in (("slow", slow), ("fast", fast)):
        await hub.connect(name, "127.0.0.1", 1)
        await transport.socket.accept()
        output = _OutboundMessages(transport.socket, hub, name, 5)
        await output.send(hub.build_hello_message())
        outputs.append(output)
    for number in range(3):
        hub.publish(snapshot(number))
        raw = hub.get_next_message("fast")
        assert raw is not None
        await outputs[1].send(raw)
    raw = hub.get_next_message("slow")
    assert raw is not None
    await outputs[0].send(raw)
    assert [m["seq"] for m in messages(fast)] == [0, 1, 2, 3]
    assert [m["data"]["meta"]["dropped_since_last"] for m in messages(fast)[1:]] == [0, 0, 0]
    assert [m["seq"] for m in messages(slow)] == [0, 3]
    assert messages(slow)[-1]["data"]["meta"]["dropped_since_last"] == 2
