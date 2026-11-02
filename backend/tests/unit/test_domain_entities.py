"""Unit tests for domain entities and the alert state machine."""

import pytest

from monitor.domain.entities import (
    Alert,
    AlertState,
    CpuSnapshot,
    DiskUsage,
    MemorySnapshot,
    SystemSnapshot,
)
from monitor.domain.types import Ok, Unavailable, UnavailableKind
from monitor.domain.values import (
    Bytes,
    LoadAverage,
    MonotonicTimestamp,
    Percent,
    SwapUsage,
    UtcTimestamp,
)


def _now(seconds: float) -> MonotonicTimestamp:

    return MonotonicTimestamp(seconds=seconds)


def _utc_now(seconds: float) -> UtcTimestamp:

    from datetime import UTC, datetime

    return UtcTimestamp(moment=datetime.fromtimestamp(seconds, tz=UTC))


def test_alert_candidate_bands() -> None:
    """Alert candidates map values onto OK/WARNING/CRITICAL bands."""

    alert = Alert(metric="cpu", state=AlertState.OK)

    assert (
        alert.candidate(value=79.0, warn_threshold=80.0, critical_threshold=95.0) is AlertState.OK
    )

    assert (
        alert.candidate(value=80.0, warn_threshold=80.0, critical_threshold=95.0)
        is AlertState.WARNING
    )

    assert (
        alert.candidate(value=95.0, warn_threshold=80.0, critical_threshold=95.0)
        is AlertState.CRITICAL
    )


def test_alert_transition_after_three_consecutive_samples() -> None:
    """OK -> WARNING requires three consecutive supporting samples."""

    alert = Alert(metric="cpu", state=AlertState.OK)

    first = alert.observe(candidate_state=AlertState.WARNING, now=_now(0.0), value=90.0)

    second = first.observe(candidate_state=AlertState.WARNING, now=_now(1.0), value=90.0)

    third = second.observe(candidate_state=AlertState.WARNING, now=_now(2.0), value=90.0)

    assert third.state is AlertState.WARNING


def test_alert_recovery_after_three_consecutive_ok_samples() -> None:
    """CRITICAL -> OK requires three consecutive OK samples."""

    alert = Alert(metric="cpu", state=AlertState.CRITICAL)

    first = alert.observe(candidate_state=AlertState.OK, now=_now(0.0), value=10.0)

    second = first.observe(candidate_state=AlertState.OK, now=_now(1.0), value=10.0)

    third = second.observe(candidate_state=AlertState.OK, now=_now(2.0), value=10.0)

    assert third.state is AlertState.OK


def test_unavailable_before_pending_transition_resets_run() -> None:
    """Unavailable after two supporting samples must not allow a same-gap transition."""

    alert = Alert(metric="cpu", state=AlertState.OK)

    first = alert.observe(candidate_state=AlertState.WARNING, now=_now(0.0), value=90.0)

    second = first.observe(candidate_state=AlertState.WARNING, now=_now(1.0), value=90.0)

    assert second.state is AlertState.OK

    after_unavailable = second.reset()

    third = after_unavailable.observe(candidate_state=AlertState.WARNING, now=_now(2.0), value=90.0)

    assert third.state is AlertState.OK

    assert third.consecutive_samples == 1


def test_disabled_before_pending_transition_resets_run() -> None:
    """Disabled after two supporting samples must not allow a same-gap transition."""

    alert = Alert(metric="cpu", state=AlertState.OK)

    first = alert.observe(candidate_state=AlertState.WARNING, now=_now(0.0), value=90.0)

    second = first.observe(candidate_state=AlertState.WARNING, now=_now(1.0), value=90.0)

    after_disabled = second.reset()

    third = after_disabled.observe(candidate_state=AlertState.WARNING, now=_now(2.0), value=90.0)

    assert third.state is AlertState.OK

    assert third.consecutive_samples == 1


def test_transition_after_three_consecutive_valid_samples_after_recovery() -> None:
    """Three consecutive valid supporting samples after a prior state produce a transition."""

    alert = Alert(metric="cpu", state=AlertState.WARNING)

    first = alert.observe(candidate_state=AlertState.CRITICAL, now=_now(0.0), value=97.0)

    second = first.observe(candidate_state=AlertState.CRITICAL, now=_now(1.0), value=97.0)

    third = second.observe(candidate_state=AlertState.CRITICAL, now=_now(2.0), value=97.0)

    assert third.state is AlertState.CRITICAL


def test_alert_state_preserved_while_unavailable_or_disabled() -> None:
    """Unavailable/disabled samples preserve the current alert state."""

    alert = Alert(metric="cpu", state=AlertState.OK)

    first = alert.observe(candidate_state=AlertState.WARNING, now=_now(0.0), value=90.0)

    second = first.observe(candidate_state=AlertState.WARNING, now=_now(1.0), value=90.0)

    after_unavailable = second.reset()

    after_disabled = after_unavailable.reset()

    assert after_unavailable.state is AlertState.OK

    assert after_disabled.state is AlertState.OK


def test_zero_percent_is_valid_ok_candidate_not_unavailable() -> None:
    """A genuine zero reading is a valid OK candidate, not unavailability."""

    alert = Alert(metric="cpu", state=AlertState.OK)

    assert alert.candidate(value=0.0, warn_threshold=80.0, critical_threshold=95.0) is AlertState.OK


def test_cpu_snapshot_validates_core_count_and_frequency() -> None:
    """CpuSnapshot validates core count and optional frequency."""

    CpuSnapshot(
        cpu_total=Percent(value=10.0),
        per_core=(None,),
        load_average=LoadAverage(value=0.0),
        core_count=1,
    )

    with pytest.raises(ValueError):
        CpuSnapshot(
            cpu_total=Percent(value=10.0),
            per_core=(None,),
            load_average=LoadAverage(value=0.0),
            core_count=0,
        )


def test_memory_snapshot_rejects_available_above_total() -> None:
    """MemorySnapshot rejects available above total."""

    with pytest.raises(ValueError):
        MemorySnapshot(
            total=Bytes(value=100),
            available=Bytes(value=200),
            used_percent=Percent(value=50.0),
            swap=SwapUsage(total=Bytes(value=0), used=Bytes(value=0)),
        )


def test_disk_usage_rejects_used_above_total() -> None:
    """DiskUsage rejects used above total."""

    with pytest.raises(ValueError):
        DiskUsage(
            device="sda",
            total=Bytes(value=100),
            used=Bytes(value=200),
            percent=Percent(value=50.0),
        )


def test_system_snapshot_assembles_phase2_groups() -> None:
    """SystemSnapshot assembles MetricResult for CPU and memory groups with dual timestamps."""

    snapshot = SystemSnapshot(
        cpu=Unavailable(kind=UnavailableKind.UNSUPPORTED, reason="test"),
        memory=Unavailable(kind=UnavailableKind.UNSUPPORTED, reason="test"),
        disk=Unavailable(kind=UnavailableKind.UNSUPPORTED, reason="test"),
        network=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming"),
        timestamp_monotonic=_now(0.0),
        timestamp_utc=_utc_now(0.0),
    )

    assert isinstance(snapshot.cpu, Unavailable)

    assert isinstance(snapshot.memory, Unavailable)

    assert snapshot.timestamp_monotonic.seconds == 0.0

    assert snapshot.timestamp_utc.moment.timestamp() == 0.0

    # Also test with Ok values

    ok_cpu = Ok(
        CpuSnapshot(
            cpu_total=Percent(value=10.0),
            per_core=(Percent(value=10.0),),
            load_average=LoadAverage(value=0.0),
            core_count=1,
        )
    )

    ok_memory = Ok(
        MemorySnapshot(
            total=Bytes(value=1024),
            available=Bytes(value=512),
            used_percent=Percent(value=50.0),
            swap=SwapUsage(total=Bytes(value=0), used=Bytes(value=0)),
        )
    )

    snapshot2 = SystemSnapshot(
        cpu=ok_cpu,
        memory=ok_memory,
        disk=Unavailable(kind=UnavailableKind.UNSUPPORTED, reason="test"),
        network=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming"),
        timestamp_monotonic=_now(1.5),
        timestamp_utc=_utc_now(1.5),
    )

    assert isinstance(snapshot2.cpu, Ok)

    assert isinstance(snapshot2.memory, Ok)

    assert snapshot2.timestamp_monotonic.seconds == 1.5
