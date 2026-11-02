"""Immutable value objects for the Linux system health domain."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

PERCENT_MAX = 100.0


@dataclass(frozen=True)
class Percent:
    """Percentage value in the inclusive range [0, 100]."""

    value: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise ValueError("percent value must be finite")
        if not 0.0 <= self.value <= PERCENT_MAX:
            raise ValueError("percent value must be within [0, 100]")


@dataclass(frozen=True)
class Bytes:
    """Non-negative byte count."""

    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise TypeError("bytes value must be an integer")
        if self.value < 0:
            raise ValueError("bytes value must be non-negative")


@dataclass(frozen=True)
class Rate:
    """Throughput measured in units per second."""

    value: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise ValueError("rate must be finite")
        if self.value < 0.0:
            raise ValueError("rate must be non-negative")

    @classmethod
    def from_counters(cls, previous: Bytes, current: Bytes, elapsed_seconds: float) -> Rate:
        """Compute reset-aware throughput from cumulative counters."""
        if not math.isfinite(elapsed_seconds) or elapsed_seconds <= 0.0:
            raise ValueError("elapsed seconds must be positive")
        delta = current.value - previous.value if current.value >= previous.value else current.value
        return cls(value=delta / elapsed_seconds)


@dataclass(frozen=True)
class LoadAverage:
    """Raw load average; dimensionless running-process count."""

    value: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise ValueError("load average must be finite")
        if self.value < 0.0:
            raise ValueError("load average must be non-negative")


@dataclass(frozen=True)
class MonotonicTimestamp:
    """Monotonic seconds for elapsed-time calculations."""

    seconds: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.seconds):
            raise ValueError("monotonic timestamp must be finite")
        if self.seconds < 0.0:
            raise ValueError("monotonic timestamp must be non-negative")


@dataclass(frozen=True)
class UtcTimestamp:
    """Timezone-aware UTC datetime."""

    moment: datetime

    def __post_init__(self) -> None:
        if self.moment.tzinfo is None or self.moment.utcoffset() != timedelta(0):
            raise ValueError("utc timestamp must be timezone-aware UTC")


@dataclass(frozen=True)
class SwapUsage:
    """Swap usage; a zero total means swap is disabled."""

    total: Bytes
    used: Bytes

    def __post_init__(self) -> None:
        if self.used.value > self.total.value:
            raise ValueError("swap used cannot exceed total")
        if self.total.value == 0 and self.used.value != 0:
            raise ValueError("swap used must be zero when total is zero")

    @property
    def percent(self) -> float:
        """Swap usage percentage; zero when swap is disabled."""
        if self.total.value <= 0:
            return 0.0
        return (self.used.value / self.total.value) * 100.0
