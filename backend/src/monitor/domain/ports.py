"""Canonical domain reader ports."""

from __future__ import annotations

from typing import Protocol

from monitor.domain.entities import (
    CpuSnapshot,
    DiskUsage,
    MemorySnapshot,
    NetCounters,
    ProcessList,
    SensorSnapshot,
)
from monitor.domain.types import MetricResult
from monitor.domain.values import MonotonicTimestamp, UtcTimestamp


class CpuReader(Protocol):
    """Port for CPU metric collection."""

    async def read(self) -> MetricResult[CpuSnapshot]: ...


class MemoryReader(Protocol):
    """Port for memory metric collection."""

    async def read(self) -> MetricResult[MemorySnapshot]: ...


class DiskReader(Protocol):
    """Port for disk metric collection."""

    async def read(self) -> MetricResult[DiskUsage]: ...


class NetReader(Protocol):
    """Port for network counter collection."""

    async def read(self) -> MetricResult[NetCounters]: ...


class ProcessReader(Protocol):
    """Port for process metric collection."""

    async def read(self) -> MetricResult[ProcessList]: ...


class SensorReader(Protocol):
    """Port for hardware sensor collection."""

    async def read(self) -> MetricResult[SensorSnapshot]: ...


class Clock(Protocol):
    """Monotonic and UTC clocks captured at sampling boundaries."""

    def monotonic(self) -> MonotonicTimestamp: ...

    def utc(self) -> UtcTimestamp: ...

    async def sleep(self, delay: float) -> None:
        """Sleep for the specified duration using the clock's time source."""
        ...
