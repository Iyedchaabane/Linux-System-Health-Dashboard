"""Unit tests for domain value objects."""

from datetime import UTC, datetime

import pytest

from monitor.domain.values import (
    Bytes,
    Percent,
    Rate,
    SwapUsage,
    UtcTimestamp,
)


def test_percent_accepts_full_range() -> None:
    """Percent accepts 0 and 100 inclusive."""
    assert Percent(value=0.0).value == 0.0
    assert Percent(value=100.0).value == 100.0


def test_percent_rejects_out_of_range_or_non_finite() -> None:
    """Percent rejects values outside [0, 100] and non-finite floats."""
    with pytest.raises(ValueError):
        Percent(value=100.1)
    with pytest.raises(ValueError):
        Percent(value=float("nan"))


def test_bytes_rejects_negative_or_boolean() -> None:
    """Bytes rejects negative counts and booleans."""
    assert Bytes(value=0).value == 0
    with pytest.raises(ValueError):
        Bytes(value=-1)
    with pytest.raises(TypeError):
        Bytes(value=True)


def test_rate_from_counters_is_reset_aware() -> None:
    """Counter resets are handled through the post-reset value."""
    rate = Rate.from_counters(
        previous=Bytes(value=100), current=Bytes(value=30), elapsed_seconds=10.0
    )
    assert rate.value == 3.0


def test_swap_usage_zero_total_means_disabled() -> None:
    """A zero swap total disables swap and yields zero percent."""
    swap = SwapUsage(total=Bytes(value=0), used=Bytes(value=0))
    assert swap.percent == 0.0


def test_swap_usage_rejects_overuse() -> None:
    """Swap usage above the total is invalid."""
    with pytest.raises(ValueError):
        SwapUsage(total=Bytes(value=10), used=Bytes(value=20))


def test_utc_timestamp_requires_aware_utc() -> None:
    """UtcTimestamp requires a timezone-aware UTC datetime."""
    assert UtcTimestamp(moment=datetime(2026, 1, 1, tzinfo=UTC)).moment == datetime(
        2026, 1, 1, tzinfo=UTC
    )
    with pytest.raises(ValueError):
        UtcTimestamp(moment=datetime(2026, 1, 1))
