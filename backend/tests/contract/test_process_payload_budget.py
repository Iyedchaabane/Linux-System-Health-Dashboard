"""Diagnostic full-snapshot budgets, not mathematical maximum-size claims.

Test-only bridge: SystemSnapshot/serialize_snapshot currently expose four groups.
We serialize those real domain models, insert the approved typed processes group,
then validate the full WS and REST models. No collector integration is implied.

Baseline: 64 logical CPUs, 25 rows with 128-character names, 1 TiB RAM,
256 TiB disk, wide cumulative network counters and 64 GiB RSS per row (RSS
can double-count shared pages). PIDs approach the common 64-bit Linux pid_max
ceiling 2**22, but stay below it; neither this nor core count bounds the schema.
Process CPU uses one logical CPU = 100%, with ties and unknown values last.
Controls are schema-valid adversarial names, not claims about typical comm data.
4096 cores demonstrate that non-process data alone can exceed the budget.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.websockets import WebSocket

from monitor.config.settings import Settings
from monitor.domain.entities import (
    CpuSnapshot,
    DiskUsage,
    MemorySnapshot,
    NetCounters,
    SystemSnapshot,
)
from monitor.domain.types import Ok
from monitor.domain.values import (
    Bytes,
    LoadAverage,
    MonotonicTimestamp,
    Percent,
    SwapUsage,
    UtcTimestamp,
)
from monitor.presentation.api.app import create_app
from monitor.presentation.api.deps import get_snapshot_provider
from monitor.presentation.api.schemas import SnapshotResponse
from monitor.presentation.ws.budget import DEGRADED_REASON
from monitor.presentation.ws.endpoint import _OutboundMessages
from monitor.presentation.ws.hub import BroadcastHub
from monitor.presentation.ws.protocol import (
    ProcessesStateOk,
    ProcessesValue,
    ProcessRow,
    ServerMessage,
)
from monitor.presentation.ws.snapshot import serialize_snapshot

BUDGET = 16_384
DEGRADED_STATE = {
    "status": "unavailable",
    "kind": "transient",
    "reason": DEGRADED_REASON,
}
NAMES = {
    "ascii": "x" * 128,
    "utf8_non_bmp": "\U0001f600" * 128,
    "utf8_mixed": "é界\U0001f600a" * 32,
    "escaped_mixed": ('"\\\x01\x1f') * 32,
    "escaped_control": "\x01" * 128,
}


def _snapshot(cores: int) -> SystemSnapshot:
    return SystemSnapshot(
        cpu=Ok(
            CpuSnapshot(
                cpu_total=Percent(87.125),
                per_core=(Percent(87.125),) * cores,
                load_average=LoadAverage(123.456),
                core_count=cores,
                frequency_hz=3_999_999_999.0,
            )
        ),
        memory=Ok(
            MemorySnapshot(
                total=Bytes(2**40),
                available=Bytes(2**38),
                used_percent=Percent(75.0),
                swap=SwapUsage(total=Bytes(2**36), used=Bytes(2**35)),
            )
        ),
        disk=Ok(
            DiskUsage(
                device="/dev/nvme0n1p1",
                total=Bytes(2**48),
                used=Bytes(2**47),
                percent=Percent(50.0),
            )
        ),
        network=Ok(
            NetCounters(
                rx_bytes=Bytes(2**53 - 1),
                tx_bytes=Bytes(2**52 + 12345),
                sampled_at=MonotonicTimestamp(123456.75),
            )
        ),
        timestamp_monotonic=MonotonicTimestamp(123456.75),
        timestamp_utc=UtcTimestamp(datetime(2026, 1, 1, tzinfo=UTC)),
    )


def _four_groups(cores: int) -> str:
    return serialize_snapshot(_snapshot(cores), seq=1)


def _degraded_names(raw_payload: dict[str, Any], emitted: dict[str, Any]) -> list[str]:
    """Return groups replaced by the documented whole-group degradation."""
    raw_groups = raw_payload["data"]["groups"]
    emitted_groups = emitted["data"]["groups"]
    assert set(emitted_groups) == set(raw_groups)
    degraded: list[str] = []
    for name, raw_group in raw_groups.items():
        emitted_group = emitted_groups[name]
        if emitted_group == raw_group:
            continue
        assert emitted_group == DEGRADED_STATE, f"{name} is not a whole-group replacement"
        assert raw_group.get("status") != "unavailable"
        degraded.append(name)
    return degraded


def _full_message(name: str, cores: int = 64) -> str:
    rows = [
        ProcessRow(
            pid=2**22 - 25 + i,
            name=name,
            cpu_percent=3210.125 - (i // 2) * 100 if i < 23 else None,
            memory_rss_bytes=2**36 + i * 4096,
        )
        for i in range(25)
    ]
    group = ProcessesStateOk(
        status="ok", partial=True, value=ProcessesValue(items=rows, skipped=12345)
    )
    payload = json.loads(_four_groups(cores))
    payload["data"]["groups"]["processes"] = group.model_dump(mode="json")
    return ServerMessage.model_validate(payload).model_dump_json()


class _CapturingSocket:
    """Only the transport boundary is fake; sender and hub are production code."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(text)


async def _outbound(raw: str, budget: int = BUDGET) -> str:
    socket = _CapturingSocket()
    hub = BroadcastHub()
    assert await hub.connect("budget", "test-ip", 4) is None
    sender = _OutboundMessages(
        cast(WebSocket, socket), hub, "budget", timeout=1.0, budget_bytes=budget
    )
    try:
        # Fixed hello avoids host time; sender assigns hello=0 and snapshot=1.
        hello_path = Path(__file__).resolve().parents[3] / "contracts/ws/v1/fixtures/hello.json"
        hello = ServerMessage.model_validate_json(hello_path.read_text(encoding="utf-8"))
        await sender.send(hello.model_dump_json())
        hub.publish(raw)
        queued = hub.get_next_message("budget")
        assert queued is not None
        await sender.send(queued)
        assert len(socket.sent) == 2
        return socket.sent[1]
    finally:
        hub.disconnect("budget", "test complete")
        assert hub.get_total_clients() == 0


@pytest.mark.parametrize("case", NAMES)
async def test_full_snapshot_integrity_and_measurement(case: str) -> None:
    name = NAMES[case]
    assert len(name) == 128
    raw = _full_message(name)
    emitted = await _outbound(raw)
    raw_payload = json.loads(raw)
    payload = json.loads(emitted)
    raw_size = len(raw.encode("utf-8"))
    emitted_size = len(emitted.encode("utf-8"))
    degraded = _degraded_names(raw_payload, payload)

    # Envelope, sequence and metadata are identical whether or not the guard ran.
    assert set(payload) == {"v", "type", "seq", "ts", "data"}
    assert (payload["v"], payload["type"], payload["seq"], payload["ts"]) == (
        1,
        "snapshot",
        1,
        1767225600000,
    )
    assert payload["ts"] == raw_payload["ts"]
    data = payload["data"]
    assert data["type"] == raw_payload["data"]["type"] == "snapshot"
    assert data["meta"] == raw_payload["data"]["meta"] == {"dropped_since_last": 0}
    assert set(data["groups"]) == {"cpu", "memory", "disk", "network", "processes"}

    if raw_size <= BUDGET:
        # The guard is a no-op: emitted bytes equal the input exactly.
        assert emitted == raw
        assert degraded == []
    else:
        # The documented whole-group replacement is the only allowed difference.
        assert emitted_size <= BUDGET
        assert degraded

    processes = data["groups"]["processes"]
    if processes["status"] == "ok":
        # Surviving rows are byte-identical: no truncation, renaming or renumbering.
        assert processes == raw_payload["data"]["groups"]["processes"]
        rows = processes["value"]["items"]
        assert len(rows) == 25
        assert all(row["name"] == name for row in rows)
        assert rows == sorted(
            rows,
            key=lambda row: (
                row["cpu_percent"] is None,
                -(row["cpu_percent"] or 0),
                row["pid"],
            ),
        )
    else:
        # A degraded processes group carries no rows at all.
        assert processes == DEGRADED_STATE
        assert "value" not in processes
        assert "items" not in processes
        assert name not in emitted

    assert ServerMessage.model_validate_json(emitted).model_dump(exclude={"data"}) == (
        ServerMessage.model_validate_json(raw).model_dump(exclude={"data"})
    )
    if not degraded:
        assert ServerMessage.model_validate_json(emitted) == ServerMessage.model_validate_json(raw)
    rest = SnapshotResponse(ts=payload["ts"], groups=data["groups"], meta=data["meta"])
    assert rest.model_dump(mode="json")["groups"] == data["groups"]
    compact_utf8 = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    assert json.loads(compact_utf8) == payload
    print(
        f"SIZE {case}: pydantic={raw_size} endpoint={emitted_size} "
        f"compact_utf8={len(compact_utf8.encode('utf-8'))} degraded={degraded}"
    )


@pytest.mark.parametrize("case", NAMES)
@pytest.mark.parametrize("serialization", ["pydantic", "endpoint"])
async def test_full_snapshot_fits_budget(case: str, serialization: str) -> None:
    assert Settings.model_fields["snapshot_size_budget_bytes"].default == BUDGET
    assert Settings.model_fields["max_processes_in_stream"].default == 25
    raw = _full_message(NAMES[case])
    emitted = await _outbound(raw)
    pre_guard = len(raw.encode("utf-8"))
    wire = len(emitted.encode("utf-8"))
    print(f"SIZE {case} {serialization}: pydantic={pre_guard} endpoint={wire}")
    if serialization == "pydantic" and pre_guard > BUDGET:
        # The pydantic payload is the guard's input, not the wire. Only the
        # emitted message is bounded, and the guard must have degraded it.
        assert _degraded_names(json.loads(raw), json.loads(emitted))
        assert wire <= BUDGET, f"{case} {serialization}: {wire} bytes exceeds {BUDGET}"
    else:
        size = pre_guard if serialization == "pydantic" else wire
        assert size <= BUDGET, f"{case} {serialization}: {size} bytes exceeds {BUDGET}"


async def test_high_core_non_process_snapshot_fits_budget() -> None:
    raw = _four_groups(4096)
    emitted = await _outbound(raw)
    raw_payload = json.loads(raw)
    payload = json.loads(emitted)
    raw_size = len(raw.encode("utf-8"))
    emitted_size = len(emitted.encode("utf-8"))
    assert raw_size > BUDGET
    assert emitted_size <= BUDGET
    assert payload["data"]["groups"]["cpu"] == DEGRADED_STATE
    for group in ("memory", "disk", "network"):
        assert payload["data"]["groups"][group] == raw_payload["data"]["groups"][group]
    print(
        f"SIZE 4096_core_non_process: pydantic={raw_size} "
        f"endpoint={emitted_size} degraded={_degraded_names(raw_payload, payload)}"
    )


class _FixedSnapshotProvider:
    """Return one deterministic snapshot without starting the sampler."""

    def __init__(self, snapshot: SystemSnapshot) -> None:
        self._snapshot = snapshot

    async def __call__(self) -> SystemSnapshot:
        return self._snapshot


async def test_rest_and_websocket_degrade_the_same_groups() -> None:
    """This high-core case agrees at seq=1/drops=0, not all transport envelopes."""
    snapshot = _snapshot(4096)
    budget = 4096
    raw = serialize_snapshot(snapshot, seq=1)
    emitted = await _outbound(raw, budget=budget)
    ws_payload = json.loads(emitted)

    app = create_app()
    app.dependency_overrides[get_snapshot_provider] = lambda: _FixedSnapshotProvider(snapshot)
    # The route reads the budget from the container; this is the only value it needs.
    app.state.container = SimpleNamespace(
        settings=Settings(snapshot_size_budget_bytes=budget)
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/snapshot")

    assert response.status_code == 200
    assert len(response.content) <= budget
    print(f"SIZE accepted REST budget={budget}: actual={len(response.content)}")
    rest = response.json()
    assert rest["ts"] == ws_payload["ts"]
    assert rest["groups"] == ws_payload["data"]["groups"]
    assert _degraded_names(json.loads(raw), ws_payload) == ["cpu"]
    assert rest["groups"]["cpu"] == DEGRADED_STATE
