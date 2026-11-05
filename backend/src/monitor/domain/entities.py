"""Domain entities for system health snapshots and alerts."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import StrEnum

from monitor.domain.types import MetricResult
from monitor.domain.values import (
    Bytes,
    LoadAverage,
    MonotonicTimestamp,
    Percent,
    Rate,
    SwapUsage,
    UtcTimestamp,
)

ALERT_CONSECUTIVE_THRESHOLD = 3
PROCESS_NAME_MAX_LENGTH = 128


class AlertState(StrEnum):
    """Alert severity bands."""

    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class CpuSnapshot:
    """Phase 2 CPU snapshot."""

    cpu_total: Percent
    per_core: tuple[Percent | None, ...]
    load_average: LoadAverage
    core_count: int
    frequency_hz: float | None = None

    def __post_init__(self) -> None:
        if isinstance(self.core_count, bool) or not isinstance(self.core_count, int):
            raise TypeError("core count must be an integer")
        if self.core_count < 1:
            raise ValueError("core count must be positive")
        if self.frequency_hz is not None and (
            not math.isfinite(self.frequency_hz) or self.frequency_hz < 0.0
        ):
            raise ValueError("frequency must be finite and non-negative")


@dataclass(frozen=True)
class MemorySnapshot:
    """Phase 2 memory snapshot."""

    total: Bytes
    available: Bytes
    used_percent: Percent
    swap: SwapUsage

    def __post_init__(self) -> None:
        if self.available.value > self.total.value:
            raise ValueError("memory available cannot exceed total")


@dataclass(frozen=True)
class DiskUsage:
    """Disk usage snapshot."""

    device: str
    total: Bytes
    used: Bytes
    percent: Percent

    def __post_init__(self) -> None:
        if self.used.value > self.total.value:
            raise ValueError("disk used cannot exceed total")


@dataclass(frozen=True)
class NetCounters:
    """Cumulative network counters."""

    rx_bytes: Bytes
    tx_bytes: Bytes
    sampled_at: MonotonicTimestamp


@dataclass(frozen=True)
class NetThroughput:
    """Derived network throughput; rates are unknown until a delta exists."""

    rx_rate: Rate | None
    tx_rate: Rate | None


@dataclass(frozen=True)
class ProcessInfo:
    """One process observed in the current PID namespace.

    Only processes visible to the monitor are represented: a container sees its
    own PID namespace, so this is not a host-wide inventory and its rows must
    never be summed into host totals. ``memory_rss_bytes`` is resident set size,
    which double-counts shared pages across processes. ``cpu_percent`` is
    ``None`` while no CPU-time delta exists for the identity (first observation
    or PID reuse) and is never a placeholder zero.
    """

    pid: int
    name: str
    cpu_percent: float | None
    memory_rss_bytes: int

    def __post_init__(self) -> None:
        if isinstance(self.pid, bool) or not isinstance(self.pid, int):
            raise TypeError("pid must be an integer")
        if self.pid <= 0:
            raise ValueError("pid must be positive")
        if not isinstance(self.name, str):
            raise TypeError("process name must be a string")
        if not self.name:
            raise ValueError("process name must not be empty")
        if len(self.name) > PROCESS_NAME_MAX_LENGTH:
            raise ValueError("process name must be at most 128 characters")
        if self.cpu_percent is not None and (
            not math.isfinite(self.cpu_percent) or self.cpu_percent < 0.0
        ):
            raise ValueError("cpu percent must be finite and non-negative")
        if isinstance(self.memory_rss_bytes, bool) or not isinstance(self.memory_rss_bytes, int):
            raise TypeError("memory rss must be an integer")
        if self.memory_rss_bytes < 0:
            raise ValueError("memory rss must be non-negative")


@dataclass(frozen=True)
class ProcessList:
    """Bounded process rows from one observation plus the skipped count.

    ``skipped`` counts processes that disappeared, were zombies or were not
    readable. Rows are capped by the collector; the cap itself is not a
    partial result.
    """

    items: tuple[ProcessInfo, ...]
    skipped: int

    def __post_init__(self) -> None:
        if isinstance(self.skipped, bool) or not isinstance(self.skipped, int):
            raise TypeError("skipped must be an integer")
        if self.skipped < 0:
            raise ValueError("skipped must be non-negative")


@dataclass(frozen=True)
class SensorSnapshot:
    """Minimal hardware sensor reading."""

    metric: str
    value: float
    unit: str

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise ValueError("sensor value must be finite")


@dataclass(frozen=True)
class Alert:
    """Alert state with three-consecutive-sample transitions."""

    metric: str
    state: AlertState
    consecutive_samples: int = 0
    last_value: float | None = None
    last_transition: MonotonicTimestamp | None = None
    last_candidate: AlertState = AlertState.OK

    def candidate(
        self, value: float, warn_threshold: float, critical_threshold: float
    ) -> AlertState:
        """Classify a value into OK, WARNING or CRITICAL bands."""
        if not math.isfinite(value):
            raise ValueError("alert value must be finite")
        if value >= critical_threshold:
            return AlertState.CRITICAL
        if value >= warn_threshold:
            return AlertState.WARNING
        return AlertState.OK

    def observe(self, candidate_state: AlertState, now: MonotonicTimestamp, value: float) -> Alert:
        """Apply one sample; state changes need three consecutive samples."""
        consecutive = self.consecutive_samples + 1 if candidate_state == self.last_candidate else 1
        new_state = self.state
        transitioned = False
        if candidate_state != self.state and consecutive >= ALERT_CONSECUTIVE_THRESHOLD:
            new_state = candidate_state
            transitioned = True
        return replace(
            self,
            state=new_state,
            consecutive_samples=consecutive,
            last_value=value,
            last_transition=now if transitioned else self.last_transition,
            last_candidate=candidate_state,
        )

    def reset(self) -> Alert:
        """Reset pending consecutive-sample state (e.g. after unavailable/disabled)."""
        return replace(self, consecutive_samples=0)


@dataclass(frozen=True)
class SystemSnapshot:
    """Phase 2 snapshot with full MetricResult and dual timestamps."""

    cpu: MetricResult[CpuSnapshot]
    memory: MetricResult[MemorySnapshot]
    disk: MetricResult[DiskUsage]
    network: MetricResult[NetCounters]
    timestamp_monotonic: MonotonicTimestamp
    timestamp_utc: UtcTimestamp
    processes: MetricResult[ProcessList] | None = None
