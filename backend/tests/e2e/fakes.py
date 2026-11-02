"""Test-only fake collectors with deterministic fake metric values."""

from __future__ import annotations

from monitor.domain.entities import (
    CpuSnapshot,
    DiskUsage,
    MemorySnapshot,
    NetCounters,
)
from monitor.domain.ports import (
    CpuReader,
    DiskReader,
    MemoryReader,
    NetReader,
)
from monitor.domain.types import MetricResult, Ok
from monitor.domain.values import (
    Bytes,
    LoadAverage,
    MonotonicTimestamp,
    Percent,
    SwapUsage,
)


class _ClockProxy:
    pass


class FakeCpuReader(CpuReader):
    async def read(self) -> MetricResult[CpuSnapshot]:
        return Ok(
            CpuSnapshot(
                cpu_total=Percent(value=42.0),
                per_core=(Percent(value=42.0), Percent(value=40.0)),
                load_average=LoadAverage(value=1.0),
                core_count=2,
                frequency_hz=1_000_000_000.0,
            )
        )


class FakeMemoryReader(MemoryReader):
    async def read(self) -> MetricResult[MemorySnapshot]:
        return Ok(
            MemorySnapshot(
                total=Bytes(value=1024),
                available=Bytes(value=384),
                used_percent=Percent(value=64.0),
                swap=SwapUsage(total=Bytes(value=0), used=Bytes(value=0)),
            )
        )


class FakeDiskReader(DiskReader):
    async def read(self) -> MetricResult[DiskUsage]:
        return Ok(
            DiskUsage(
                device="/",
                total=Bytes(value=1000),
                used=Bytes(value=250),
                percent=Percent(value=25.0),
            )
        )


class FakeNetworkReader(NetReader):
    async def read(self) -> MetricResult[NetCounters]:
        # Fixed sampled_at monotonic value per test start
        return Ok(
            NetCounters(
                rx_bytes=Bytes(value=1_200_000),
                tx_bytes=Bytes(value=800_000),
                sampled_at=MonotonicTimestamp(seconds=1.0),
            )
        )
