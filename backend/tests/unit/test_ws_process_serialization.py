"""Tests for the WebSocket v1 processes group serialization."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

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
from monitor.presentation.ws.protocol import ProcessesValue, ProcessRow
from monitor.presentation.ws.snapshot import serialize_snapshot


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


def _serialized(snapshot: SystemSnapshot, seq: int = 1, dropped: int = 0) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(serialize_snapshot(snapshot, seq=seq, dropped=dropped))
    return payload


def test_ok_processes_group_keeps_collector_order_and_values() -> None:
    """Rows keep the collector's order; None and >100 are preserved verbatim."""
    items = (
        ProcessInfo(pid=10, name="busy", cpu_percent=250.0, memory_rss_bytes=2048),
        ProcessInfo(pid=20, name="fresh", cpu_percent=None, memory_rss_bytes=0),
        ProcessInfo(pid=30, name="idle", cpu_percent=0.0, memory_rss_bytes=512),
    )
    result = Ok(ProcessList(items=items, skipped=7, total=5), partial=True)

    payload = _serialized(_snapshot(result), seq=9)
    group = payload["data"]["groups"]["processes"]

    assert group["status"] == "ok"
    assert group["partial"] is True
    assert group["value"]["skipped"] == 7
    assert group["value"]["total"] == 5
    assert group["value"]["total"] != group["value"]["skipped"] + len(items)
    assert group["value"]["items"] == [
        {"pid": 10, "name": "busy", "cpu_percent": 250.0, "memory_rss_bytes": 2048},
        {"pid": 20, "name": "fresh", "cpu_percent": None, "memory_rss_bytes": 0},
        {"pid": 30, "name": "idle", "cpu_percent": 0.0, "memory_rss_bytes": 512},
    ]


def test_unavailable_processes_group_reports_kind_and_reason() -> None:
    """An unavailable collector result is explicit, never empty rows."""
    result = Unavailable(UnavailableKind.PERMISSION, "Process information is not readable.")

    group = _serialized(_snapshot(result))["data"]["groups"]["processes"]

    assert group == {
        "status": "unavailable",
        "kind": "permission",
        "reason": "Process information is not readable.",
    }


def test_absent_processes_result_omits_key_and_keeps_the_envelope() -> None:
    """A snapshot without a processes result keeps the four legacy groups only."""
    payload = _serialized(_snapshot(None), seq=3, dropped=2)

    assert set(payload) == {"v", "type", "seq", "ts", "data"}
    assert payload["v"] == 1
    assert payload["type"] == "snapshot"
    assert payload["seq"] == 3
    assert payload["data"]["type"] == "snapshot"
    assert payload["data"]["meta"] == {"dropped_since_last": 2}
    assert set(payload["data"]["groups"]) == {"cpu", "memory", "disk", "network"}
    assert payload["data"]["groups"]["cpu"]["value"]["cpu_total"] == 12.5
    assert payload["data"]["groups"]["network"]["value"]["rx_bytes"] == 1000

    with_processes = _serialized(_snapshot(Ok(ProcessList(items=(), skipped=0, total=0))), seq=3, dropped=2)

    assert with_processes["ts"] == payload["ts"]
    assert with_processes["data"]["meta"] == payload["data"]["meta"]
    for name in ("cpu", "memory", "disk", "network"):
        assert with_processes["data"]["groups"][name] == payload["data"]["groups"][name]
    assert set(with_processes["data"]["groups"]) == {
        "cpu",
        "memory",
        "disk",
        "network",
        "processes",
    }


def test_processes_value_accepts_total_equal_to_and_above_items() -> None:
    """``total`` covers the returned rows and may exceed them before the cap."""
    row = ProcessRow(pid=1, name="p", cpu_percent=None, memory_rss_bytes=0)

    at_least = ProcessesValue(items=[row], skipped=0, total=1)
    above = ProcessesValue(items=[row], skipped=0, total=5)

    assert at_least.total == 1
    assert above.total == 5
    assert above.total >= len(above.items)


@pytest.mark.parametrize(
    "payload",
    [
        {"items": [], "skipped": 0},
        {"items": [], "skipped": 0, "total": -1},
        {"items": [], "skipped": 0, "total": True},
        {
            "items": [
                {"pid": 1, "name": "p", "cpu_percent": None, "memory_rss_bytes": 0}
            ],
            "skipped": 0,
            "total": 0,
        },
    ],
    ids=["missing", "negative", "bool", "below_items"],
)
def test_processes_value_rejects_invalid_total(payload: dict[str, Any]) -> None:
    """A missing, negative, boolean or too-small total is not a valid payload."""
    with pytest.raises(ValidationError):
        ProcessesValue.model_validate(payload)


def test_processes_value_still_forbids_unknown_fields() -> None:
    """The added field did not relax the model's strict extra-field policy."""
    with pytest.raises(ValidationError):
        ProcessesValue.model_validate(
            {"items": [], "skipped": 0, "total": 0, "unexpected": 1}
        )
