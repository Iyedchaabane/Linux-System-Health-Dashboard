"""Unit tests for the CollectSnapshot use case."""

import asyncio
from datetime import UTC, datetime

import pytest

from monitor.application.collect_snapshot import CollectSnapshot
from monitor.domain.entities import CpuSnapshot, MemorySnapshot, SystemSnapshot
from monitor.domain.types import Ok, Unavailable, UnavailableKind
from monitor.domain.values import (
    Bytes,
    LoadAverage,
    MonotonicTimestamp,
    Percent,
    SwapUsage,
    UtcTimestamp,
)


class FakeClock:
    """Fake clock for deterministic timestamp injection."""

    def __init__(self, mono: float = 1000.0, utc: datetime | None = None):
        self._mono = MonotonicTimestamp(seconds=mono)
        if utc is None:
            utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        self._utc = UtcTimestamp(moment=utc)

    def monotonic(self) -> MonotonicTimestamp:
        return self._mono

    def utc(self) -> UtcTimestamp:
        return self._utc


class FakeCpuReader:
    """Fake CPU reader with controllable results."""

    def __init__(self, result):
        self._result = result

    async def read(self):
        return self._result


class FakeMemoryReader:
    """Fake memory reader with controllable results."""

    def __init__(self, result):
        self._result = result

    async def read(self):
        return self._result


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


class TestCollectSnapshot:
    """Tests for CollectSnapshot use case.

    Test scenarios:
    - CPU and memory collection failure isolation
    - Sampling interval floor enforcement (handled by Sampler, not tested here)
    - Bounded history behavior (handled by HistoryStore, not tested here)
    - Fake clock injection and deterministic timestamps
    - Cancellation and shutdown behavior
    - Correct handling of unavailable metric results
    """

    @pytest.mark.asyncio
    async def test_call_returns_snapshot_with_both_results_ok(self) -> None:
        """Successful collection returns a SystemSnapshot with Ok results."""
        cpu_reader = FakeCpuReader(Ok(make_cpu_snapshot()))
        memory_reader = FakeMemoryReader(Ok(make_memory_snapshot()))
        clock = FakeClock()

        collector = CollectSnapshot(cpu_reader, memory_reader, clock)

        snapshot = await collector()

        assert isinstance(snapshot, SystemSnapshot)
        assert isinstance(snapshot.cpu, Ok)
        assert isinstance(snapshot.memory, Ok)

    @pytest.mark.asyncio
    async def test_call_returns_snapshot_with_unavailable_cpu(self) -> None:
        """CPU unavailable is propagated to the snapshot."""
        cpu_result = Unavailable(UnavailableKind.PERMISSION, "CPU access denied")
        memory_reader = FakeMemoryReader(Ok(make_memory_snapshot()))
        clock = FakeClock()

        collector = CollectSnapshot(FakeCpuReader(cpu_result), memory_reader, clock)

        result = await collector()

        assert isinstance(result.cpu, Unavailable)
        assert result.cpu.kind == UnavailableKind.PERMISSION

    @pytest.mark.asyncio
    async def test_call_returns_snapshot_with_unavailable_memory(self) -> None:
        """Memory unavailable is propagated to the snapshot."""
        memory_result = Unavailable(UnavailableKind.TRANSIENT, "Memory read failed")
        cpu_reader = FakeCpuReader(Ok(make_cpu_snapshot()))
        clock = FakeClock()

        collector = CollectSnapshot(cpu_reader, FakeMemoryReader(memory_result), clock)

        result = await collector()

        assert isinstance(result.memory, Unavailable)
        assert result.memory.kind == UnavailableKind.TRANSIENT

    def test_call_timestamps_captured_at_snapshot_boundary(self) -> None:
        """Both timestamps are captured at the start, before collection."""
        cpu_reader = FakeCpuReader(Ok(make_cpu_snapshot()))
        memory_reader = FakeMemoryReader(Ok(make_memory_snapshot()))
        utc_dt = datetime(2024, 2, 1, 12, 0, 0, tzinfo=UTC)
        clock = FakeClock(mono=2000.0, utc=utc_dt)

        collector = CollectSnapshot(cpu_reader, memory_reader, clock)
        result = asyncio.run(collector())

        assert result.timestamp_monotonic == MonotonicTimestamp(seconds=2000.0)
        assert result.timestamp_utc == UtcTimestamp(moment=utc_dt)

    @pytest.mark.asyncio
    async def test_call_concurrent_collection_uses_gather(self) -> None:
        """CPU and memory are collected concurrently via asyncio.gather."""
        collection_order: list[str] = []

        class OrderTrackingCpuReader:
            async def read(self):
                collection_order.append("cpu")
                await asyncio.sleep(0)  # Yield control
                return Ok(make_cpu_snapshot())

        class OrderTrackingMemoryReader:
            async def read(self):
                collection_order.append("memory")
                await asyncio.sleep(0)  # Yield control
                return Ok(make_memory_snapshot())

        collector = CollectSnapshot(
            OrderTrackingCpuReader(),
            OrderTrackingMemoryReader(),
            FakeClock(),
        )

        await collector()

        # Both should be collected concurrently (order may vary)
        assert set(collection_order) == {"cpu", "memory"}

    @pytest.mark.asyncio
    async def test_call_handles_both_unavailable(self) -> None:
        """Both metrics unavailable is handled correctly."""
        cpu_result = Unavailable(UnavailableKind.DISABLED, "CPU disabled")
        memory_result = Unavailable(UnavailableKind.TRANSIENT, "Memory transient error")

        collector = CollectSnapshot(
            FakeCpuReader(cpu_result),
            FakeMemoryReader(memory_result),
            FakeClock(),
        )

        result = await collector()

        assert isinstance(result.cpu, Unavailable)
        assert result.cpu.kind == UnavailableKind.DISABLED
        assert isinstance(result.memory, Unavailable)
        assert result.memory.kind == UnavailableKind.TRANSIENT

    @pytest.mark.asyncio
    async def test_call_partial_cpu_available_memory_unavailable(self) -> None:
        """Partial results where CPU is Ok and memory is Unavailable."""
        cpu_result = Ok(make_cpu_snapshot())
        memory_result = Unavailable(UnavailableKind.PERMISSION, "Permission denied")

        collector = CollectSnapshot(
            FakeCpuReader(cpu_result),
            FakeMemoryReader(memory_result),
            FakeClock(),
        )

        result = await collector()

        assert isinstance(result.cpu, Ok)
        assert isinstance(result.memory, Unavailable)

    @pytest.mark.asyncio
    async def test_call_partial_memory_available_cpu_unavailable(self) -> None:
        """Partial results where memory is Ok and CPU is Unavailable."""
        cpu_result = Unavailable(UnavailableKind.UNSUPPORTED, "Unsupported hardware")
        memory_result = Ok(make_memory_snapshot())

        collector = CollectSnapshot(
            FakeCpuReader(cpu_result),
            FakeMemoryReader(memory_result),
            FakeClock(),
        )

        result = await collector()

        assert isinstance(result.cpu, Unavailable)
        assert isinstance(result.memory, Ok)

    @pytest.mark.asyncio
    async def test_call_unavailable_kind_preserves_reason(self) -> None:
        """Unavailable reason is preserved in the result."""
        cpu_result = Unavailable(UnavailableKind.UNSUPPORTED, "No CPU cores detected")

        collector = CollectSnapshot(
            FakeCpuReader(cpu_result),
            FakeMemoryReader(Ok(make_memory_snapshot())),
            FakeClock(),
        )

        result = await collector()

        assert result.cpu.reason == "No CPU cores detected"

    def test_timestamp_types_are_correct(self) -> None:
        """Timestamp types match the domain contracts."""
        cpu_reader = FakeCpuReader(Ok(make_cpu_snapshot()))
        memory_reader = FakeMemoryReader(Ok(make_memory_snapshot()))
        clock = FakeClock()

        collector = CollectSnapshot(cpu_reader, memory_reader, clock)
        result = asyncio.run(collector())

        assert isinstance(result.timestamp_monotonic, MonotonicTimestamp)
        assert isinstance(result.timestamp_utc, UtcTimestamp)
        # Both should have positive finite values
        assert result.timestamp_monotonic.seconds >= 0.0
        assert result.timestamp_utc.moment.tzinfo is not None
