"""Composition tests for the process collector wiring."""

from __future__ import annotations

from typing import Any

import pytest

import monitor.composition as composition
from monitor.config import Settings
from monitor.domain.entities import (
    CpuSnapshot,
    DiskUsage,
    MemorySnapshot,
    NetCounters,
    ProcessInfo,
    ProcessList,
)
from monitor.domain.types import Ok
from monitor.domain.values import (
    Bytes,
    LoadAverage,
    MonotonicTimestamp,
    Percent,
    SwapUsage,
)
from monitor.infrastructure.psutil_process import PsutilProcessReader


def _ok_cpu() -> Ok[CpuSnapshot]:
    return Ok(
        CpuSnapshot(
            cpu_total=Percent(value=10.0),
            per_core=(Percent(value=10.0),),
            load_average=LoadAverage(value=0.5),
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


def _ok_disk() -> Ok[DiskUsage]:
    return Ok(
        DiskUsage(
            device="/", total=Bytes(value=1000), used=Bytes(value=250), percent=Percent(value=25.0)
        )
    )


def _ok_network() -> Ok[NetCounters]:
    return Ok(
        NetCounters(
            rx_bytes=Bytes(value=1200),
            tx_bytes=Bytes(value=800),
            sampled_at=MonotonicTimestamp(seconds=1.0),
        )
    )


def test_process_reader_uses_the_stream_cap_setting() -> None:
    """The wired reader carries the non-default max_processes_in_stream cap."""
    container = composition.build_container(Settings(max_processes_in_stream=7))

    try:
        assert isinstance(container.process_reader, PsutilProcessReader)
        # The cap has no public accessor; assert the value the setting produced.
        assert container.process_reader._max_processes == 7
        assert container.cleanup_callback == container.process_reader.close
    finally:
        if container.cleanup_callback is not None:
            container.cleanup_callback()


async def test_snapshot_provider_passes_the_process_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The container's provider returns the process result, never DISABLED."""
    expected = Ok(
        ProcessList(
            items=(
                ProcessInfo(pid=42, name="wired", cpu_percent=None, memory_rss_bytes=1),
            ),
            skipped=0,
        )
    )
    seen_caps: list[int] = []
    closed: list[FakeProcessReader] = []

    class FakeProcessReader:
        def __init__(self, max_processes: int = 25) -> None:
            seen_caps.append(max_processes)

        async def read(self):
            return expected

        def close(self) -> None:
            closed.append(self)

    class FakeReader:
        def __init__(self, result: Any) -> None:
            self._result = result

        async def read(self):
            return self._result

    monkeypatch.setattr(composition, "PsutilProcessReader", FakeProcessReader)
    monkeypatch.setattr(composition, "PsutilCpuReader", lambda: FakeReader(_ok_cpu()))
    monkeypatch.setattr(composition, "PsutilMemoryReader", lambda: FakeReader(_ok_memory()))
    monkeypatch.setattr(composition, "PsutilDiskReader", lambda: FakeReader(_ok_disk()))
    monkeypatch.setattr(composition, "PsutilNetworkReader", lambda: FakeReader(_ok_network()))

    container = composition.build_container(Settings(max_processes_in_stream=9))
    try:
        snapshot = await container.snapshot_provider()

        assert seen_caps == [9]
        assert snapshot.processes is expected
        assert snapshot.processes.value.items[0].pid == 42
        assert container.cleanup_callback is not None
    finally:
        if container.cleanup_callback is not None:
            container.cleanup_callback()
    assert closed == [container.process_reader]
