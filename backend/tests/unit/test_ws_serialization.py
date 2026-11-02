"""Tests for the ws snapshot serializer."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from monitor.domain.entities import (
    CpuSnapshot,
    DiskUsage,
    MemorySnapshot,
    NetCounters,
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
from monitor.presentation.ws.snapshot import serialize_snapshot


def _now(seconds: float) -> MonotonicTimestamp:
    return MonotonicTimestamp(seconds=seconds)


def _utc_now(seconds: float) -> UtcTimestamp:
    moment = datetime.fromtimestamp(seconds, tz=UTC)
    return UtcTimestamp(moment=moment)


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


def _snapshot(disk: MetricResult[Any], network: MetricResult[Any]) -> SystemSnapshot:
    return SystemSnapshot(
        cpu=Ok(_ok_cpu()),
        memory=Ok(_ok_memory()),
        disk=disk,
        network=network,
        timestamp_monotonic=MonotonicTimestamp(seconds=1.0),
        timestamp_utc=_utc_now(1.0),
    )


class TestWsSerialization:
    def test_network_available(self) -> None:
        s = _snapshot(Ok(_ok_disk()), Ok(_ok_network()))
        payload = json.loads(serialize_snapshot(s, seq=7))
        net = payload["data"]["groups"]["network"]
        assert net["status"] == "ok"
        assert net["value"]["rx_bytes"] == 1000
        assert net["value"]["tx_bytes"] == 500
        assert "cpu" in payload["data"]["groups"]
        assert "memory" in payload["data"]["groups"]
        assert "disk" in payload["data"]["groups"]

    def test_network_unavailable(self) -> None:
        net = Unavailable(kind=UnavailableKind.PERMISSION, reason="denied")
        s = _snapshot(Ok(_ok_disk()), net)
        payload = json.loads(serialize_snapshot(s, seq=3))
        assert payload["data"]["groups"]["network"]["status"] == "unavailable"
        assert payload["data"]["groups"]["network"]["kind"] == "permission"

    def test_seq_propagation(self) -> None:
        s = _snapshot(Ok(_ok_disk()), Ok(_ok_network()))
        payload = json.loads(serialize_snapshot(s, seq=42))
        assert payload["seq"] == 42
