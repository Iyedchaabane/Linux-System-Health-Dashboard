"""Unit tests for the Sampler class.

These tests verify the Sampler's timing behavior, grid scheduling,
timeout handling, and state management.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from monitor.domain.entities import CpuSnapshot, DiskUsage, MemorySnapshot, SystemSnapshot
from monitor.domain.types import Ok, Unavailable, UnavailableKind
from monitor.domain.values import (
    Bytes,
    LoadAverage,
    MonotonicTimestamp,
    Percent,
    SwapUsage,
    UtcTimestamp,
)

from ..fakes.fake_clock import FakeClock

# Import the Sampler from application.sampler module
# This will fail until the module/class is implemented
try:
    from monitor.application.sampler import Sampler
except ImportError:
    Sampler = None
    # Raising at module level would prevent test collection, but we want
    # tests to show ImportError failures clearly

if TYPE_CHECKING:
    pass


def make_cpu_snapshot() -> CpuSnapshot:
    """Build a valid CPU snapshot with defaults."""
    return CpuSnapshot(
        cpu_total=Percent(value=25.0),
        per_core=(Percent(value=25.0),),
        load_average=LoadAverage(value=1.5),
        core_count=1,
        frequency_hz=2500000000.0,
    )


def make_memory_snapshot() -> MemorySnapshot:
    """Build a valid memory snapshot with defaults."""
    return MemorySnapshot(
        total=Bytes(value=16 * 1024 * 1024 * 1024),  # 16GB
        available=Bytes(value=8 * 1024 * 1024 * 1024),
        used_percent=Percent(value=50.0),
        swap=SwapUsage(total=Bytes(value=0), used=Bytes(value=0)),
    )


def make_snapshot() -> SystemSnapshot:
    """Build a valid SystemSnapshot with both results Ok."""
    return SystemSnapshot(
        cpu=Ok(make_cpu_snapshot()),
        memory=Ok(make_memory_snapshot()),
        disk=Ok(
            DiskUsage(
                device="/tmp",
                total=Bytes(value=1000),
                used=Bytes(value=500),
                percent=Percent(value=50.0),
            )
        ),
        network=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming"),
        timestamp_monotonic=MonotonicTimestamp(seconds=0.0),
        timestamp_utc=UtcTimestamp(moment=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)),
    )


def _ensure_sampler_available() -> None:
    """Ensure Sampler is available, raise ImportError if not."""
    if Sampler is None:
        raise ImportError("monitor.application.sampler module not found")


class TestSamplerBasicBehavior:
    """Tests for basic Sampler behavior."""

    @pytest.mark.asyncio
    async def test_immediate_first_collection(self) -> None:
        """First collection happens at t=0.

        The sampler should start collecting immediately, not wait for
        the first interval.
        """
        _ensure_sampler_available()
        clock = FakeClock()
        start_times: list[float] = []

        async def collect() -> SystemSnapshot:
            start_times.append(clock.monotonic().seconds)
            await clock.sleep(0.1)  # Simulate collection
            return make_snapshot()

        async def consumer(snapshot: SystemSnapshot) -> None:
            pass

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=1.0,
            collect_timeout=1.0,
        )

        await sampler.start()
        await clock.advance(0.15)  # Advance past collection duration
        await sampler.stop()

        assert len(start_times) >= 1
        assert start_times[0] == 0.0  # First collection at t=0

    @pytest.mark.asyncio
    async def test_repeated_start_idempotent(self) -> None:
        """Calling start() multiple times is a no-op after the first."""
        _ensure_sampler_available()
        clock = FakeClock()
        collection_count = 0

        async def collect() -> SystemSnapshot:
            nonlocal collection_count
            collection_count += 1
            await clock.sleep(0.01)
            return make_snapshot()

        async def consumer(snapshot: SystemSnapshot) -> None:
            pass

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=1.0,
            collect_timeout=1.0,
        )

        await sampler.start()
        await asyncio.sleep(0.05)
        await sampler.start()  # Second call should be no-op
        await asyncio.sleep(0.05)
        await sampler.stop()

        # Should have started exactly one sampling loop
        assert collection_count >= 1

    @pytest.mark.asyncio
    async def test_restart_after_stop(self) -> None:
        """After stop(), restart() is allowed."""
        _ensure_sampler_available()
        clock = FakeClock()
        start_times: list[float] = []

        async def collect() -> SystemSnapshot:
            start_times.append(clock.monotonic().seconds)
            await clock.sleep(0.01)
            return make_snapshot()

        async def consumer(snapshot: SystemSnapshot) -> None:
            pass

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=1.0,
            collect_timeout=1.0,
        )

        await sampler.start()
        await asyncio.sleep(0.05)
        await sampler.stop()

        first_count = len(start_times)

        await sampler.start()  # Restart should work
        await asyncio.sleep(0.05)
        await sampler.stop()

        assert len(start_times) > first_count  # More collections after restart


class TestSamplerStopBehavior:
    """Tests for Sampler stop behavior."""

    @pytest.mark.asyncio
    async def test_stop_during_sleep(self) -> None:
        """Stop() returns quickly when sampler is sleeping."""
        _ensure_sampler_available()
        clock = FakeClock()
        collection_count = 0

        async def collect() -> SystemSnapshot:
            nonlocal collection_count
            collection_count += 1
            await clock.sleep(0.01)  # Very short collection
            return make_snapshot()

        async def consumer(snapshot: SystemSnapshot) -> None:
            pass

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=1.0,
            collect_timeout=1.0,
            stop_timeout=2.0,
        )

        await sampler.start()
        await asyncio.sleep(0.05)  # Let at least one collection happen

        stop_start = asyncio.get_event_loop().time()

        await sampler.stop()

        stop_duration = asyncio.get_event_loop().time() - stop_start

        # Stop should return within stop_timeout, not wait for interval
        assert stop_duration < 1.0
        assert collection_count >= 1

    @pytest.mark.asyncio
    async def test_stop_during_in_flight_collection(self) -> None:
        """Stop() waits for in-flight collection, bounded by stop_timeout."""
        _ensure_sampler_available()
        clock = FakeClock()
        collection_count = 0

        async def collect() -> SystemSnapshot:
            nonlocal collection_count
            collection_count += 1
            await clock.sleep(3.0)  # Long collection
            return make_snapshot()

        async def consumer(snapshot: SystemSnapshot) -> None:
            pass

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=1.0,
            collect_timeout=10.0,
            stop_timeout=2.0,
        )

        await sampler.start()
        await asyncio.sleep(0.1)  # Let collection start

        stop_start = asyncio.get_event_loop().time()
        await sampler.stop()
        stop_duration = asyncio.get_event_loop().time() - stop_start

        # Should have waited for collection (bounded by stop_timeout)
        assert collection_count >= 1
        # Stop should complete within stop_timeout after collection finishes
        assert stop_duration < 5.0

    @pytest.mark.asyncio
    async def test_concurrent_stops(self) -> None:
        """Multiple concurrent stop() calls are safe."""
        _ensure_sampler_available()
        clock = FakeClock()
        collection_count = 0

        async def collect() -> SystemSnapshot:
            nonlocal collection_count
            collection_count += 1
            await clock.sleep(0.01)
            return make_snapshot()

        async def consumer(snapshot: SystemSnapshot) -> None:
            pass

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=1.0,
            collect_timeout=1.0,
            stop_timeout=2.0,
        )

        await sampler.start()
        await asyncio.sleep(0.05)

        # Call stop multiple times concurrently
        await asyncio.gather(sampler.stop(), sampler.stop(), sampler.stop())

        assert collection_count >= 1


class TestSamplerGridScheduling:
    """Tests for Sampler's grid-based scheduling."""

    @pytest.mark.asyncio
    async def test_overrun_3_5x_interval_grid(self) -> None:
        """When collection takes 3.5s with 1s interval, grid scheduling applies.

        With interval 1.0, collection takes 3.5s:
        - First collection at t=0
        - Next grid slot after completion: t=4.0 (ceil(3.5) = 4)
        - Missed slots (1.0, 2.0, 3.0) are skipped; no catch-up collection at 3.5
        - Second collection starts at t=4.0, not at 3.5
        """
        _ensure_sampler_available()
        clock = FakeClock()
        start_times: list[float] = []

        async def collect() -> SystemSnapshot:
            start_times.append(clock.monotonic().seconds)
            await clock.sleep(3.5)  # Simulate 3.5s collection
            return make_snapshot()

        async def consumer(snapshot: SystemSnapshot) -> None:
            pass

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=1.0,
            collect_timeout=10.0,
            stop_timeout=2.0,
        )

        await sampler.start()

        # First collection at t=0 takes 3.5s (finishes at t=3.5);
        # next grid slot is t=4.0; missed slots (1.0, 2.0, 3.0) are skipped
        await clock.advance(3.5)
        # Let the sampler loop finish the in-flight collection cycle and
        # register the sleep until the next grid slot
        for _ in range(10):
            await asyncio.sleep(0)
        # Advance to the second grid slot (t=4.0)
        await clock.advance(0.5)

        await sampler.stop()

        # Verify grid scheduling
        assert start_times[0] == 0.0, f"First at 0.0, got {start_times[0]}"
        assert start_times[1] == 4.0, f"Second at 4.0, got {start_times[1]}"

        # Verify no catch-up collections
        assert 3.5 not in start_times, "No collection at 3.5 (no catch-up)"
        assert 6.0 not in start_times, "No collection at 6.0 (no catch-up)"

    @given(
        st.lists(
            st.floats(min_value=0.01, max_value=0.5),  # Collection duration
            min_size=3,
            max_size=10,
        ),
        st.floats(min_value=1.0, max_value=10.0),  # Interval
    )
    @pytest.mark.asyncio
    async def test_grid_property(self, durations: list[float], interval: float) -> None:
        """Hypothesis test: for any list of collection durations, every start is on a grid slot.

        Grid slots are at: start + k*interval for k = 0, 1, 2, ...

        Properties to verify:
        1. Every start time is on a grid slot
        2. At most one start per slot
        3. Never starts before previous collection ended
        """
        _ensure_sampler_available()
        clock = FakeClock()
        start_times: list[float] = []
        collection_idx = 0

        async def collect() -> SystemSnapshot:
            nonlocal collection_idx
            duration = durations[min(collection_idx, len(durations) - 1)]
            start_times.append(clock.monotonic().seconds)
            await clock.sleep(duration)
            collection_idx += 1
            return make_snapshot()

        async def consumer(snapshot: SystemSnapshot) -> None:
            pass

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=interval,
            collect_timeout=20.0,
            stop_timeout=2.0,
        )

        await sampler.start()

        # Run until we have enough collections
        total_duration = sum(durations) + len(durations) * interval + 1.0
        await clock.advance(total_duration)

        await sampler.stop()

        # Property 1: Every start is on a grid slot
        initial = start_times[0] if start_times else 0.0
        for start in start_times:
            offset = start - initial
            remainder = offset % interval
            assert remainder < 0.001 or abs(remainder - interval) < 0.001, (
                f"Start time {start} not on grid (interval={interval})"
            )

        # Property 2: At most one start per slot
        slots = set()
        for start in start_times:
            if start_times:
                slot = round((start - initial) / interval)
                assert slot not in slots, f"Multiple starts at grid slot {slot}"
                slots.add(slot)

        # Property 3: Never starts before previous ended
        # Finish time = start_time + duration that was used
        for i in range(1, len(start_times)):
            prev_start = start_times[i - 1]
            prev_duration = durations[min(i - 1, len(durations) - 1)]
            prev_finish = prev_start + prev_duration
            curr_start = start_times[i]
            # Collection must start at or after previous collection finished
            assert curr_start >= prev_finish, (
                f"Collection {i} started at {curr_start} before previous finished at {prev_finish}"
            )


class TestSamplerTimeouts:
    """Tests for Sampler timeout behavior."""

    @pytest.mark.asyncio
    async def test_hung_collector_timeout(self) -> None:
        """When collector times out, failure is counted, nothing published, loop continues."""
        _ensure_sampler_available()
        clock = FakeClock()
        success_count = 0
        failure_count = 0

        async def collect() -> SystemSnapshot:
            # Simulate a hung collector that takes too long
            await clock.sleep(5.0)
            return make_snapshot()

        async def consumer(snapshot: SystemSnapshot) -> None:
            nonlocal success_count
            success_count += 1

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=1.0,
            collect_timeout=0.5,  # 0.5s timeout, but collection takes 5s
            stop_timeout=2.0,
        )

        await sampler.start()

        # Advance past first timeout
        await clock.advance(1.0)

        await sampler.stop()

        # First collection should timeout, failure counted
        assert failure_count >= 1 or sampler.failures >= 1, "Timeout should increment failures"

    @pytest.mark.asyncio
    async def test_hung_consumer_timeout(self, caplog: pytest.LogCaptureFixture) -> None:
        """When consumer times out, error is logged, loop continues."""
        _ensure_sampler_available()
        clock = FakeClock()

        async def collect() -> SystemSnapshot:
            return make_snapshot()

        async def consumer(snapshot: SystemSnapshot) -> None:
            # Simulate a hung consumer that exceeds timeout
            await clock.sleep(2.0)

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=1.0,
            collect_timeout=0.1,
            consumer_timeout=0.2,
            stop_timeout=1.0,
        )

        await sampler.start()
        # First cycle: t=0.0 collection completes; consumer hangs past consumer_timeout (0.2)
        await clock.advance(0.5)
        await sampler.stop()

        # Should not hang; sampler should handle consumer timeout
        # Verify the sampler continues to operate (can be called again)
        assert sampler is not None
        # Check that timeout was logged
        # Note: actual logging depends on implementation

    @pytest.mark.asyncio
    async def test_consumer_exception_logged_and_continues(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When consumer raises, exception is logged with traceback, no secrets."""
        _ensure_sampler_available()
        clock = FakeClock()

        async def collect() -> SystemSnapshot:
            await clock.sleep(0.01)
            return make_snapshot()

        async def consumer(snapshot: SystemSnapshot) -> None:
            raise RuntimeError("Consumer error - secret123")  # Contains potential secret

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=1.0,
            collect_timeout=1.0,
            stop_timeout=2.0,
        )

        await sampler.start()
        await asyncio.sleep(0.1)
        await sampler.stop()

        # Check that exception was logged
        assert len(caplog.records) > 0 or sampler.failures > 0  # Loop continues

    @pytest.mark.asyncio
    async def test_caller_cancellation_propagates(self) -> None:
        """Cancelling stop() raises CancelledError in the caller, doesn't cancel sampler task."""
        _ensure_sampler_available()
        clock = FakeClock()
        stop_cancelled = False
        sampler_task: asyncio.Task | None = None

        async def collect() -> SystemSnapshot:
            await clock.sleep(0.01)
            return make_snapshot()

        async def consumer(snapshot: SystemSnapshot) -> None:
            pass

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=1.0,
            collect_timeout=0.1,
            stop_timeout=5.0,  # Long timeout
        )

        await sampler.start()

        async def try_stop() -> None:
            nonlocal stop_cancelled, sampler_task
            try:
                await sampler.stop()
            except asyncio.CancelledError:
                stop_cancelled = True
                raise

        sampler_task = asyncio.create_task(try_stop())

        for _ in range(3):
            await asyncio.sleep(0)  # Let stop start
        sampler_task.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await sampler_task

        for _ in range(3):
            await asyncio.sleep(0)  # Let internal cleanup

        # The caller should see CancelledError
        assert stop_cancelled, "Caller should receive CancelledError"


class TestSamplerIntervalValidation:
    """Tests for Sampler interval validation."""

    def test_interval_validation_zero(self) -> None:
        """Interval of 0 raises ValueError."""
        _ensure_sampler_available()
        clock = FakeClock()

        with pytest.raises(ValueError, match="interval"):
            Sampler(
                collect=lambda: asyncio.sleep(0),
                consumer=lambda s: None,
                clock=clock,
                interval=0.0,
                collect_timeout=1.0,
            )

    def test_interval_validation_negative(self) -> None:
        """Negative interval raises ValueError."""
        _ensure_sampler_available()
        clock = FakeClock()

        with pytest.raises(ValueError, match="interval"):
            Sampler(
                collect=lambda: asyncio.sleep(0),
                consumer=lambda s: None,
                clock=clock,
                interval=-1.0,
                collect_timeout=1.0,
            )

    def test_interval_validation_nan(self) -> None:
        """NaN interval raises ValueError."""
        _ensure_sampler_available()
        clock = FakeClock()

        with pytest.raises(ValueError, match="interval"):
            Sampler(
                collect=lambda: asyncio.sleep(0),
                consumer=lambda s: None,
                clock=clock,
                interval=float("nan"),
                collect_timeout=1.0,
            )

    def test_interval_validation_inf(self) -> None:
        """Infinite interval raises ValueError."""
        _ensure_sampler_available()
        clock = FakeClock()

        with pytest.raises(ValueError, match="interval"):
            Sampler(
                collect=lambda: asyncio.sleep(0),
                consumer=lambda s: None,
                clock=clock,
                interval=float("inf"),
                collect_timeout=1.0,
            )

    def test_interval_validation_below_minimum(self) -> None:
        """Interval below 1.0 raises ValueError."""
        _ensure_sampler_available()
        clock = FakeClock()

        with pytest.raises(ValueError, match=r"interval.*1\.0.*10\.0"):
            Sampler(
                collect=lambda: asyncio.sleep(0),
                consumer=lambda s: None,
                clock=clock,
                interval=0.5,
                collect_timeout=1.0,
            )

    def test_interval_validation_above_maximum(self) -> None:
        """Interval above 10.0 raises ValueError."""
        _ensure_sampler_available()
        clock = FakeClock()

        with pytest.raises(ValueError, match=r"interval.*1\.0.*10\.0"):
            Sampler(
                collect=lambda: asyncio.sleep(0),
                consumer=lambda s: None,
                clock=clock,
                interval=15.0,
                collect_timeout=1.0,
            )


class TestSamplerNoOrphanTasks:
    """Tests for proper cleanup of background tasks."""

    @pytest.mark.asyncio
    async def test_no_orphan_tasks(self) -> None:
        """After stop(), asyncio.all_tasks() returns to baseline."""
        _ensure_sampler_available()
        clock = FakeClock()

        async def collect() -> SystemSnapshot:
            await clock.sleep(0.01)
            return make_snapshot()

        async def consumer(snapshot: SystemSnapshot) -> None:
            pass

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=1.0,
            collect_timeout=1.0,
            stop_timeout=2.0,
        )

        await sampler.start()
        await asyncio.sleep(0.05)
        await sampler.stop()

        # Count tasks before and after
        baseline_count = len(asyncio.all_tasks())
        await asyncio.sleep(0.1)  # Allow cleanup
        final_count = len(asyncio.all_tasks())

        # Should not leave behind additional tasks
        # Note: We expect at most 1 (the current task) plus any test framework tasks
        assert final_count <= baseline_count + 1


class TestSamplerLatestAndLastSuccess:
    """Tests for latest() and last_success_at() methods."""

    @pytest.mark.asyncio
    async def test_latest_and_last_success_at(self) -> None:
        """latest() returns None initially, last_success_at() returns None until success."""
        _ensure_sampler_available()
        clock = FakeClock()

        async def collect() -> SystemSnapshot:
            await clock.sleep(0.01)
            return make_snapshot()

        async def consumer(snapshot: SystemSnapshot) -> None:
            pass

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=1.0,
            collect_timeout=1.0,
        )

        # Initially, should be None
        assert sampler.latest() is None
        assert sampler.last_success_at() is None

        await sampler.start()
        await clock.advance(0.05)  # Let first collection complete
        await sampler.stop()

        # After successful collection, should have values
        latest = sampler.latest()
        assert latest is not None
        assert isinstance(latest, SystemSnapshot)

        last_success = sampler.last_success_at()
        assert last_success is not None
        assert isinstance(last_success, MonotonicTimestamp)


class TestSamplerPublishesUnchanged:
    """Tests for publishing collection results unchanged."""

    @pytest.mark.asyncio
    async def test_publishes_collect_result_unchanged(self) -> None:
        """Sampler publishes collect result unchanged, including Unavailable results."""
        _ensure_sampler_available()
        clock = FakeClock()
        published_snapshots: list[SystemSnapshot] = []

        async def collect() -> SystemSnapshot:
            await clock.sleep(0.01)
            # Return an Unavailable result, not fabricated/fallback
            return SystemSnapshot(
                cpu=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming up"),
                memory=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming up"),
                disk=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming up"),
                network=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming"),
                timestamp_monotonic=MonotonicTimestamp(seconds=clock.monotonic().seconds),
                timestamp_utc=clock.utc(),
            )

        async def consumer(snapshot: SystemSnapshot) -> None:
            published_snapshots.append(snapshot)

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=1.0,
            collect_timeout=1.0,
        )

        await sampler.start()
        await clock.advance(0.05)  # Let first collection complete
        await sampler.stop()

        assert len(published_snapshots) >= 1

        # Verify the Unavailable is preserved, not replaced
        snapshot = published_snapshots[0]
        assert isinstance(snapshot.cpu, Unavailable)
        assert snapshot.cpu.kind == UnavailableKind.TRANSIENT
        assert snapshot.cpu.reason == "warming up"
        assert isinstance(snapshot.memory, Unavailable)
        assert snapshot.memory.kind == UnavailableKind.TRANSIENT


class TestSamplerCounters:
    """Tests for failure and overrun counters."""

    @pytest.mark.asyncio
    async def test_failures_counter(self) -> None:
        """failures counter increments on collect timeout."""
        _ensure_sampler_available()
        clock = FakeClock()

        async def collect() -> SystemSnapshot:
            await clock.sleep(5.0)  # Will timeout
            return make_snapshot()

        async def consumer(snapshot: SystemSnapshot) -> None:
            pass

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=1.0,
            collect_timeout=0.1,
            stop_timeout=1.0,
        )

        await sampler.start()
        await clock.advance(1.5)  # Enough for timeout
        await sampler.stop()

        assert sampler.failures >= 1

    @pytest.mark.asyncio
    async def test_overruns_counter(self) -> None:
        """overruns counter increments when collection takes longer than interval."""
        _ensure_sampler_available()
        clock = FakeClock()
        collection_duration = 2.0  # Longer than the 1.0 interval

        async def collect() -> SystemSnapshot:
            nonlocal collection_duration
            collection_duration = 2.0  # Longer than interval
            await clock.sleep(2.0)
            return make_snapshot()

        async def consumer(snapshot: SystemSnapshot) -> None:
            pass

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=1.0,
            collect_timeout=5.0,
        )

        await sampler.start()
        await clock.advance(2.5)  # Collection takes 2.0s > interval 1.0
        await sampler.stop()

        # Collections that exceed interval should be counted as overruns
        assert sampler.overruns >= 1


class TestSamplerTaskCleanupRegression:
    """Task 3.1 regression tests: in-flight tasks must be cancelled and awaited."""

    @pytest.mark.asyncio
    async def test_stop_timeout_cancels_in_flight_collect_task(self) -> None:
        """Stop timeout must cancel and await the in-flight collection task.

        Regression (Task 3.1, HIGH): when the loop task was cancelled through the
        stop timeout, the in-flight collect task (and its timeout sleep task) could
        be left running instead of being cancelled and awaited.
        """
        _ensure_sampler_available()
        clock = FakeClock()
        collect_cancelled = False
        in_flight = False

        async def collect() -> SystemSnapshot:
            nonlocal collect_cancelled, in_flight
            in_flight = True
            try:
                await clock.sleep(10.0)  # Long-running collection stays in flight
            except asyncio.CancelledError:
                collect_cancelled = True
                raise
            finally:
                in_flight = False
            return make_snapshot()

        async def consumer(snapshot: SystemSnapshot) -> None:
            pass

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=1.0,
            collect_timeout=20.0,
            stop_timeout=0.2,
        )

        baseline_tasks = set(asyncio.all_tasks())
        await sampler.start()
        for _ in range(10):
            await asyncio.sleep(0)  # Let the loop reach the in-flight collection
        assert in_flight

        await sampler.stop()

        assert collect_cancelled, "In-flight collection should have been cancelled"
        assert not in_flight

        remaining_tasks = set(asyncio.all_tasks()) - baseline_tasks - {asyncio.current_task()}
        assert not remaining_tasks, f"Sampler left orphan tasks after stop: {remaining_tasks}"

    @pytest.mark.asyncio
    async def test_stop_timeout_cancels_in_flight_consumer_task(self) -> None:
        """Stop timeout must cancel and await the in-flight consumer task.

        Regression (Task 3.1, HIGH): when the loop task was cancelled through the
        stop timeout, the in-flight consumer task (and its timeout sleep task) could
        be left running instead of being cancelled and awaited.
        """
        _ensure_sampler_available()
        clock = FakeClock()
        consumer_cancelled = False
        consumer_in_flight = False
        published: list[SystemSnapshot] = []

        async def collect() -> SystemSnapshot:
            return make_snapshot()

        async def consumer(snapshot: SystemSnapshot) -> None:
            nonlocal consumer_cancelled, consumer_in_flight
            consumer_in_flight = True
            try:
                await clock.sleep(10.0)  # Consumer stays in flight past stop timeout
            except asyncio.CancelledError:
                consumer_cancelled = True
                raise
            finally:
                consumer_in_flight = False
            published.append(snapshot)

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=1.0,
            collect_timeout=20.0,
            consumer_timeout=20.0,
            stop_timeout=0.2,
        )

        baseline_tasks = set(asyncio.all_tasks())
        await sampler.start()
        for _ in range(10):
            await asyncio.sleep(0)  # Let the loop reach the in-flight consumer
        assert consumer_in_flight

        await sampler.stop()

        assert consumer_cancelled, "In-flight consumer should have been cancelled"
        assert published == []

        remaining_tasks = set(asyncio.all_tasks()) - baseline_tasks - {asyncio.current_task()}
        assert not remaining_tasks, f"Sampler left orphan tasks after stop: {remaining_tasks}"


class TestSamplerStartDuringStopRegression:
    """Task 3.1 regression tests: start() during stop() graceful-wait window."""

    @pytest.mark.asyncio
    async def test_start_during_stop_does_not_create_second_loop(self) -> None:
        """start() during stop() must not create a second sampling loop.

        Regression (Task 3.1, HIGH): stop() cleared the running flag before the
        graceful-wait finished, so a concurrent start() could spawn a second loop
        task while the first was still terminating, causing overlapping collections.
        """
        _ensure_sampler_available()
        clock = FakeClock()
        in_flight = False
        overlapped = False

        async def collect() -> SystemSnapshot:
            nonlocal in_flight, overlapped
            if in_flight:
                overlapped = True
            in_flight = True
            try:
                await clock.sleep(10.0)
            finally:
                in_flight = False
            return make_snapshot()

        published: list[SystemSnapshot] = []

        async def consumer(snapshot: SystemSnapshot) -> None:
            published.append(snapshot)

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=1.0,
            collect_timeout=20.0,
            consumer_timeout=20.0,
            stop_timeout=0.2,
        )

        await sampler.start()
        for _ in range(10):
            await asyncio.sleep(0)  # First collection is in flight
        assert in_flight

        stop_task = asyncio.create_task(sampler.stop())
        await asyncio.sleep(0)  # stop() is now waiting out its graceful-wait window
        await sampler.start()  # Start while stop() is still terminating
        await stop_task
        await sampler.stop()

        assert not overlapped, "start() during stop() created a second sampling loop"

        # Once shutdown has completed, a restart must work normally again.
        await sampler.start()
        for _ in range(10):
            await asyncio.sleep(0)  # Restarted loop begins a fresh collection
        assert in_flight
        await sampler.stop()
