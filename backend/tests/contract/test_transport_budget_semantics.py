"""Same cached snapshot, transport-dependent availability at exact UTF-8 limits."""

import asyncio
import json
from collections import deque
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient, Response

from monitor.config.settings import Settings
from monitor.domain.entities import ProcessInfo, ProcessList, SystemSnapshot
from monitor.domain.types import Ok, Unavailable, UnavailableKind
from monitor.domain.values import MonotonicTimestamp, UtcTimestamp
from monitor.presentation.api.app import create_app
from monitor.presentation.api.deps import get_snapshot_provider
from monitor.presentation.ws import budget as budget_module
from monitor.presentation.ws import endpoint
from monitor.presentation.ws.budget import DEGRADED_REASON, compact_json
from monitor.presentation.ws.hub import BroadcastHub
from monitor.presentation.ws.protocol import ServerMessage
from monitor.presentation.ws.snapshot import serialize_snapshot
from tests.fakes.ws_transport import WsTransport

BUDGET = 4096
TS = 1767225600000
GROUPS = ("cpu", "memory", "disk", "network", "processes")
DEGRADED = {"status": "unavailable", "kind": "transient", "reason": DEGRADED_REASON}


def _snapshot(*, terminal: bool = False, extra_unicode: int = 0) -> SystemSnapshot:
    disabled = Unavailable(UnavailableKind.DISABLED, "synthetic disabled")
    groups: dict[str, Any] = dict.fromkeys(GROUPS, disabled)
    if terminal:
        for name, count in zip(GROUPS, (512, 512, 71, 0, extra_unicode), strict=True):
            groups[name] = Unavailable(
                UnavailableKind.DISABLED, "é" * count + "x" * (512 - count)
            )
    else:
        lengths = [128] * 16 + [27] + [1] * 8
        groups["processes"] = Ok(ProcessList(
            items=tuple(ProcessInfo(pid, "p" * length, 1.0, 1)
                        for pid, length in enumerate(lengths, start=1)),
            skipped=0,
        ))
    return SystemSnapshot(
        **groups,
        timestamp_monotonic=MonotonicTimestamp(1.0),
        timestamp_utc=UtcTimestamp(datetime(2026, 1, 1, tzinfo=UTC)),
    )


async def _rest(snapshot: SystemSnapshot) -> Response:
    app = create_app()

    async def cached_snapshot() -> SystemSnapshot:
        return snapshot

    app.dependency_overrides[get_snapshot_provider] = lambda: cached_snapshot
    app.state.container = SimpleNamespace(settings=Settings(snapshot_size_budget_bytes=BUDGET))

    @app.middleware("http")
    async def correlation(request: Any, call_next: Any) -> Any:
        request.state.request_id = "transport-budget-test"
        return await call_next(request)

    # No lifespan: the actual route runs, but no collectors or sampler start.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get("/api/v1/snapshot")


class _ControlledHub(BroadcastHub):
    """Scripted port inputs, NOT a simulation or proof of real queue overflow."""

    def __init__(self, raw: str, preceding_pings: int, drops: int) -> None:
        super().__init__()
        ping = ServerMessage.model_validate({
            "v": 1, "type": "ping", "seq": 0, "ts": TS, "data": {"type": "ping"},
        }).model_dump_json()
        self.pending = deque([ping] * preceding_pings + [raw])
        self.drops = 0
        self.snapshot_drops = drops

    def build_hello_message(self) -> str:
        path = Path(__file__).resolve().parents[3] / "contracts/ws/v1/fixtures/hello.json"
        return ServerMessage.model_validate_json(path.read_text(encoding="utf-8")).model_dump_json()

    def get_next_message(self, client_id: str) -> str | None:
        if not self.pending:
            return None
        raw = self.pending.popleft()
        if json.loads(raw)["type"] == "snapshot":
            self.drops = self.snapshot_drops
        return raw

    def get_client_drops(self, client_id: str) -> int:
        return self.drops


async def _websocket(
    raw: str, preceding_pings: int, drops: int, monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    hub = _ControlledHub(raw, preceding_pings, drops)
    transport = WsTransport(hub)
    transport.socket.app.state.container.settings = Settings(snapshot_size_budget_bytes=BUDGET)
    outbound_instances: list[endpoint._OutboundMessages] = []
    real_outbound = endpoint._OutboundMessages

    def capture_outbound(*args: Any, **kwargs: Any) -> endpoint._OutboundMessages:
        sender = real_outbound(*args, **kwargs)
        outbound_instances.append(sender)
        return sender

    async def disconnect_after_snapshot(frame: dict[str, Any]) -> None:
        if frame["type"] == "websocket.send" and json.loads(frame["text"])["type"] == "snapshot":
            transport.incoming.put_nowait({"type": "websocket.disconnect", "code": 1000})

    transport.on_send = disconnect_after_snapshot
    before = asyncio.all_tasks()
    with monkeypatch.context() as patch:
        # Observe the real sender's delivery accounting without replacing behavior.
        patch.setattr(endpoint, "_OutboundMessages", capture_outbound)
        task = asyncio.create_task(endpoint.metrics_ws(transport.socket))
        try:
            await asyncio.wait_for(task, timeout=1.0)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    assert asyncio.all_tasks() == before
    assert hub.get_total_clients() == hub.get_clients_per_ip("127.0.0.1") == 0
    assert not hub.pending
    frames = [frame for frame in transport.sent if frame["type"] == "websocket.send"]
    messages = [json.loads(frame["text"]) for frame in frames]
    assert [message["type"] for message in messages[:1]] == ["hello"]
    assert [message["seq"] for message in messages[:1 + preceding_pings]] == list(
        range(1 + preceding_pings)
    )
    assert all(message["type"] == "ping" for message in messages[1:1 + preceding_pings])
    return transport.sent, messages, outbound_instances[0]._delivered_drops


@pytest.mark.parametrize(
    ("preceding_pings", "drops", "seq", "pre_size", "wire_size"),
    [(0, 0, 1, 4096, 4096), (9, 0, 10, 4097, 558),
     (0, 9, 10, 4097, 558), (0, 10, 11, 4098, 559)],
)
async def test_same_process_snapshot_rest_available_ws_envelope_can_degrade(
    preceding_pings: int, drops: int, seq: int, pre_size: int, wire_size: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _snapshot()
    original_domain = deepcopy(asdict(snapshot))
    raw = serialize_snapshot(snapshot, seq=1)
    original = json.loads(raw)
    assert len(raw.encode("utf-8")) == BUDGET
    expected = deepcopy(original)
    expected["seq"] = seq
    expected["data"]["meta"]["dropped_since_last"] = drops
    assert len(compact_json(expected).encode("utf-8")) == pre_size

    # Both routes consume the same source object, never each other's fitted groups.
    rest = await _rest(snapshot)
    assert rest.status_code == 200
    assert len(rest.content) == 4017 <= BUDGET
    assert rest.json() == {"ts": TS, "groups": original["data"]["groups"], "meta": None}
    frames, messages, acknowledged = await _websocket(raw, preceding_pings, drops, monkeypatch)
    snapshots = [message for message in messages if message["type"] == "snapshot"]
    assert len(snapshots) == 1
    if pre_size > BUDGET:
        expected["data"]["groups"]["processes"] = DEGRADED
    assert snapshots[0] == expected
    text = next(frame["text"] for frame in frames
                if frame["type"] == "websocket.send" and json.loads(frame["text"])["type"] == "snapshot")
    assert len(text.encode("utf-8")) == wire_size <= BUDGET
    assert ServerMessage.model_validate_json(text)
    assert acknowledged == drops
    assert serialize_snapshot(snapshot, seq=1) == raw
    assert asdict(snapshot) == original_domain
    # A later REST read must still return all 25 rows with original names/values.
    again = await _rest(snapshot)
    assert again.content == rest.content
    print(f"TRANSPORT processes seq={seq} drops={drops} canonical=4096 pre={pre_size} "
          f"REST=200/4017 WS={wire_size}/{expected['data']['groups']['processes']['status']}")


@pytest.mark.parametrize("extra_unicode", [0, 1])
async def test_unavailable_unicode_boundary_rest_can_fit_while_ws_fails_closed(
    extra_unicode: int, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    snapshot = _snapshot(terminal=True, extra_unicode=extra_unicode)
    original_domain = deepcopy(asdict(snapshot))
    raw = serialize_snapshot(snapshot, seq=1)
    original = json.loads(raw)
    canonical_size = BUDGET + extra_unicode
    assert len(raw.encode("utf-8")) == canonical_size
    assert all(len(group["reason"]) == 512 for group in original["data"]["groups"].values())
    final = deepcopy(original)
    final["seq"] = 10
    assert len(compact_json(final).encode("utf-8")) == canonical_size + 1

    rest = await _rest(snapshot)
    if extra_unicode:
        assert rest.status_code == 503
        assert rest.json() == {"error": {
            "code": "INTERNAL_ERROR", "message": "Internal server error",
            "request_id": "transport-budget-test",
        }}
    else:
        assert rest.status_code == 200
        assert len(rest.content) == 4017 <= BUDGET
        assert rest.json() == {"ts": TS, "groups": original["data"]["groups"], "meta": None}
    # Isolate the WS terminal diagnostic from REST's process-wide log throttle.
    caplog.clear()
    monkeypatch.setattr(budget_module, "_last_terminal_warning", None)
    frames, messages, acknowledged = await _websocket(raw, 9, 0, monkeypatch)
    assert [message["type"] for message in messages] == ["hello"] + ["ping"] * 9
    assert frames[-1] == {"type": "websocket.close", "code": 1011, "reason": "Internal error"}
    assert [record.getMessage() for record in caplog.records
            if record.name == budget_module.__name__] == [
        f"snapshot budget exceeded: budget={BUDGET} size={canonical_size + 1}"
    ]
    assert not [record for record in caplog.records if record.levelname in {"ERROR", "CRITICAL"}]
    assert acknowledged == 0  # No snapshot was sent, so no false delivery acknowledgement.
    assert serialize_snapshot(snapshot, seq=1) == raw
    assert asdict(snapshot) == original_domain
    print(f"TRANSPORT unavailable canonical={canonical_size} seq=10 drops=0 "
          f"pre={canonical_size + 1} REST={rest.status_code}/{len(rest.content)} "
          "WS=1011/zero-snapshots")
