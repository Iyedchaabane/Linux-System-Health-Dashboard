"""Integration tests for the REST processes group of /api/v1/snapshot."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import psutil
import pytest
from httpx import ASGITransport, AsyncClient
from starlette.websockets import WebSocket

import monitor.infrastructure.psutil_process as process_module
from monitor.config.settings import Settings
from monitor.domain.entities import (
    CpuSnapshot,
    DiskUsage,
    MemorySnapshot,
    NetCounters,
    ProcessInfo,
    ProcessList,
    SystemSnapshot,
)
from monitor.domain.types import MetricResult, Ok, Unavailable, UnavailableKind
from monitor.domain.values import (
    Bytes,
    LoadAverage,
    MonotonicTimestamp,
    Percent,
    SwapUsage,
    UtcTimestamp,
)
from monitor.infrastructure.psutil_process import PsutilProcessReader
from monitor.presentation.api.app import create_app
from monitor.presentation.api.deps import get_snapshot_provider
from monitor.presentation.ws.budget import DEGRADED_REASON
from monitor.presentation.ws.endpoint import _OutboundMessages
from monitor.presentation.ws.hub import BroadcastHub
from monitor.presentation.ws.snapshot import serialize_snapshot

pytestmark = pytest.mark.integration

DEGRADED_STATE = {
    "status": "unavailable",
    "kind": "transient",
    "reason": DEGRADED_REASON,
}


def _ok_cpu() -> CpuSnapshot:
    return CpuSnapshot(
        cpu_total=Percent(value=12.5),
        per_core=(Percent(value=12.5),),
        load_average=LoadAverage(value=0.0),
        core_count=1,
    )


def _ok_memory() -> MemorySnapshot:
    return MemorySnapshot(
        total=Bytes(value=1024),
        available=Bytes(value=512),
        used_percent=Percent(value=50.0),
        swap=SwapUsage(total=Bytes(value=0), used=Bytes(value=0)),
    )


def _ok_disk() -> DiskUsage:
    return DiskUsage(
        device="/", total=Bytes(value=1024), used=Bytes(value=512), percent=Percent(value=50.0)
    )


def _ok_network() -> NetCounters:
    return NetCounters(
        rx_bytes=Bytes(value=1000),
        tx_bytes=Bytes(value=500),
        sampled_at=MonotonicTimestamp(seconds=1.0),
    )


def _snapshot(processes: MetricResult[ProcessList] | None) -> SystemSnapshot:
    return SystemSnapshot(
        cpu=Ok(_ok_cpu()),
        memory=Ok(_ok_memory()),
        disk=Ok(_ok_disk()),
        network=Ok(_ok_network()),
        timestamp_monotonic=MonotonicTimestamp(seconds=1.0),
        timestamp_utc=UtcTimestamp(moment=datetime.fromtimestamp(1.0, tz=UTC)),
        processes=processes,
    )


def _rows(count: int) -> tuple[ProcessInfo, ...]:
    return tuple(
        ProcessInfo(
            pid=1000 + index,
            name=f"process-{index:02d}-" + "x" * 110,
            cpu_percent=100.0 + index,
            memory_rss_bytes=2**20 + index,
        )
        for index in range(count)
    )


async def _get_snapshot(snapshot: SystemSnapshot, *, budget: int | None = None) -> dict[str, Any]:
    app = create_app()

    async def provider() -> SystemSnapshot:
        return snapshot

    app.dependency_overrides[get_snapshot_provider] = lambda: provider
    if budget is not None:
        app.state.container = SimpleNamespace(settings=Settings(snapshot_size_budget_bytes=budget))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/snapshot")

    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


async def test_rest_processes_match_the_websocket_group_for_the_same_snapshot() -> None:
    """Both transports expose the same values and order for one snapshot."""
    result = Ok(ProcessList(items=_rows(3), skipped=4, total=7), partial=True)
    snapshot = _snapshot(result)

    body = await _get_snapshot(snapshot)
    ws_payload = json.loads(serialize_snapshot(snapshot))

    assert body["ts"] == ws_payload["ts"]
    assert body["groups"]["processes"] == ws_payload["data"]["groups"]["processes"]
    assert body["groups"]["processes"]["value"]["skipped"] == 4
    assert body["groups"]["processes"]["value"]["total"] == 7
    assert body["groups"]["processes"]["partial"] is True
    assert [row["pid"] for row in body["groups"]["processes"]["value"]["items"]] == [
        1000,
        1001,
        1002,
    ]
    assert body["groups"]["processes"]["value"]["items"][0]["cpu_percent"] == 100.0


async def test_rest_omits_processes_when_the_snapshot_has_no_result() -> None:
    """No process result means no processes key, not an empty fake group."""
    body = await _get_snapshot(_snapshot(None))

    assert "processes" not in body["groups"]
    assert set(body["groups"]) == {"cpu", "memory", "disk", "network"}


async def test_rest_maps_unavailable_processes() -> None:
    """An unavailable collector result is mapped with its kind and reason."""
    result = Unavailable(UnavailableKind.PERMISSION, "Process information is not readable.")

    body = await _get_snapshot(_snapshot(result))

    assert body["groups"]["processes"] == {
        "status": "unavailable",
        "kind": "permission",
        "reason": "Process information is not readable.",
    }


async def test_budget_guard_degrades_the_whole_processes_group_without_rows() -> None:
    """A tight budget replaces the group wholesale; it never truncates rows."""
    result = Ok(ProcessList(items=_rows(25), skipped=0, total=25))
    snapshot = _snapshot(result)

    raw = json.loads(serialize_snapshot(snapshot))
    assert raw["data"]["groups"]["processes"]["status"] == "ok"
    assert len(raw["data"]["groups"]["processes"]["value"]["items"]) == 25

    body = await _get_snapshot(snapshot, budget=4096)

    processes = body["groups"]["processes"]
    assert processes == DEGRADED_STATE
    assert "value" not in processes
    assert "items" not in processes
    assert body["groups"]["cpu"]["status"] == "ok"


async def test_invalid_inventory_names_are_isolated_through_rest_and_ws(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real collection, serialization and outbound encoding preserve healthy groups."""
    settings = Settings()
    clock = SimpleNamespace(now=100.0)
    monkeypatch.setattr(process_module, "time", SimpleNamespace(monotonic=lambda: clock.now))
    names = [" e\u0301🛠 ", "\ud800", "bad\udcffname", "a" * 127 + "\udfff", "a" * 140 + "\ud800"]
    counters = SimpleNamespace(user=10.0, system=0.0)
    inventory = {
        pid: SimpleNamespace(
            pid=pid,
            create_time=lambda: 1.0,
            status=lambda: psutil.STATUS_RUNNING,
            name=lambda name=name: name,
            cpu_times=lambda: counters,
            memory_info=lambda: SimpleNamespace(rss=2048),
        )
        for pid, name in enumerate(names, start=1)
    }
    monkeypatch.setattr(psutil, "process_iter", lambda: list(inventory.values()))
    monkeypatch.setattr(psutil, "Process", lambda pid: inventory[pid])
    reader = PsutilProcessReader()
    await reader.read()
    clock.now = 101.0
    counters.user = 12.0
    result = await reader.read()
    assert isinstance(result, Ok)
    assert set(reader._previous) == {(1, 1.0)}
    snapshot = _snapshot(result)
    raw = serialize_snapshot(snapshot)
    raw.encode("utf-8", errors="strict")

    frames: list[dict[str, Any]] = []

    async def capture(message: dict[str, Any]) -> None:
        frames.append(message)

    inbound = iter([{"type": "websocket.connect"}])

    async def receive() -> dict[str, Any]:
        return next(inbound)

    socket = WebSocket({"type": "websocket"}, receive=receive, send=capture)
    await socket.accept()
    hub = BroadcastHub()
    assert await hub.connect("test-client", "test-ip", 4) is None
    try:
        outbound = _OutboundMessages(
            socket,
            hub,
            "test-client",
            settings.ws_send_timeout_seconds,
            budget_bytes=settings.snapshot_size_budget_bytes,
        )
        await outbound.send(raw)
    finally:
        await hub.close()
    text = frames[-1]["text"]
    assert len(text.encode("utf-8", errors="strict")) <= settings.snapshot_size_budget_bytes
    ws_groups = json.loads(text)["data"]["groups"]

    app = create_app()

    async def provider() -> SystemSnapshot:
        return snapshot

    app.dependency_overrides[get_snapshot_provider] = lambda: provider
    app.state.container = SimpleNamespace(settings=settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/snapshot")
    assert response.status_code == 200
    response.content.decode("utf-8", errors="strict")
    assert len(response.content) <= settings.snapshot_size_budget_bytes
    assert response.json()["groups"] == ws_groups
    assert ws_groups["processes"] == {
        "status": "ok",
        "partial": True,
        "value": {
            "items": [{"pid": 1, "name": names[0], "cpu_percent": 200.0, "memory_rss_bytes": 2048}],
            "skipped": 4,
            "total": 1,
        },
    }
    for group in ("cpu", "memory", "disk", "network"):
        assert ws_groups[group]["status"] == "ok"
        assert ws_groups[group] == json.loads(raw)["data"]["groups"][group]


async def test_process_total_excludes_skipped_and_is_not_derivable_from_rows() -> None:
    """``total`` counts readable processes only; skipped is never added to it."""
    result = Ok(ProcessList(items=_rows(2), skipped=4, total=3))

    body = await _get_snapshot(_snapshot(result))

    value = body["groups"]["processes"]["value"]
    assert value["total"] == 3
    assert value["total"] >= len(value["items"])
    assert value["total"] != value["skipped"] + len(value["items"])
