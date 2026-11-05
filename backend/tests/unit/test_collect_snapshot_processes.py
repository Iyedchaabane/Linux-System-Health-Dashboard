"""Unit tests for process collection inside the CollectSnapshot use case."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from monitor.application.collect_snapshot import CollectSnapshot
from monitor.domain.entities import (
    CpuSnapshot,
    MemorySnapshot,
    ProcessInfo,
    ProcessList,
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


class FixedClock:
    """Clock with a fixed monotonic and UTC reading."""

    def monotonic(self) -> MonotonicTimestamp:
        return MonotonicTimestamp(seconds=1000.0)

    def utc(self) -> UtcTimestamp:
        return UtcTimestamp(moment=datetime(2024, 1, 1, tzinfo=UTC))


class FixedReader:
    """Reader returning one pre-built result."""

    def __init__(self, result: Any) -> None:
        self._result = result

    async def read(self) -> Any:
        return self._result


def _ok_cpu() -> Ok[CpuSnapshot]:
    return Ok(
        CpuSnapshot(
            cpu_total=Percent(value=25.0),
            per_core=(Percent(value=25.0),),
            load_average=LoadAverage(value=1.5),
            core_count=1,
        )
    )


def _ok_memory() -> Ok[MemorySnapshot]:
    return Ok(
        MemorySnapshot(
            total=Bytes(value=1024),
            available=Bytes(value=512),
            used_percent=Percent(value=50.0),
            swap=SwapUsage(total=Bytes(value=0), used=Bytes(value=0)),
        )
    )


def _process_result() -> Ok[ProcessList]:
    return Ok(
        ProcessList(
            items=(
                ProcessInfo(pid=7, name="worker", cpu_percent=None, memory_rss_bytes=4096),
            ),
            skipped=0,
        ),
        partial=True,
    )


async def test_missing_process_reader_is_disabled() -> None:
    """Without a process reader the group is explicitly disabled, not empty."""
    collector = CollectSnapshot(FixedReader(_ok_cpu()), FixedReader(_ok_memory()), FixedClock())

    snapshot = await collector()

    assert isinstance(snapshot.processes, Unavailable)
    assert snapshot.processes.kind == UnavailableKind.DISABLED
    assert snapshot.processes.reason == "Process reader not configured"


async def test_process_reader_result_is_propagated_unchanged() -> None:
    """The reader's result, including partial, lands on snapshot.processes."""
    result = _process_result()
    collector = CollectSnapshot(
        FixedReader(_ok_cpu()),
        FixedReader(_ok_memory()),
        FixedClock(),
        process_reader=FixedReader(result),
    )

    snapshot = await collector()

    assert snapshot.processes is result
    assert snapshot.processes.partial is True
    assert snapshot.processes.value.items[0].pid == 7


async def test_process_collection_runs_concurrently_with_cpu_and_memory() -> None:
    """All three readers start before any of them completes."""

    class ConcurrencyProbe:
        def __init__(self) -> None:
            self.started: list[str] = []
            self.violations: list[str] = []

        def enter(self, name: str) -> None:
            self.started.append(name)

        def finish(self, name: str) -> None:
            if len(self.started) < 3:
                self.violations.append(name)

    probe = ConcurrencyProbe()

    class ProbeReader:
        def __init__(self, name: str, result: Any) -> None:
            self._name = name
            self._result = result

        async def read(self) -> Any:
            probe.enter(self._name)
            await asyncio.sleep(0)
            probe.finish(self._name)
            return self._result

    collector = CollectSnapshot(
        ProbeReader("cpu", _ok_cpu()),
        ProbeReader("memory", _ok_memory()),
        FixedClock(),
        process_reader=ProbeReader("processes", _process_result()),
    )

    await collector()

    assert probe.violations == []
    assert set(probe.started) == {"cpu", "memory", "processes"}
