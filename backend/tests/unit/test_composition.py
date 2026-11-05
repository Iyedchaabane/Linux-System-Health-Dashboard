"""Unit tests for the composition root container."""

from monitor.application.collect_snapshot import CollectSnapshot
from monitor.composition import Container, build_container
from monitor.config import Settings
from monitor.infrastructure.psutil_cpu import PsutilCpuReader
from monitor.infrastructure.psutil_disk import PsutilDiskReader
from monitor.infrastructure.psutil_memory import PsutilMemoryReader
from monitor.infrastructure.psutil_network import PsutilNetworkReader
from monitor.infrastructure.psutil_process import PsutilProcessReader
from monitor.infrastructure.system_clock import SystemClock


def test_build_container_returns_container_with_settings() -> None:
    """build_container returns a Container carrying validated settings."""
    container = build_container(Settings())
    assert isinstance(container, Container)
    assert container.settings is not None
    assert container.settings.host == "127.0.0.1"
    assert container.settings.sample_interval_seconds == 1.0


def test_container_components_wired_in_phase2() -> None:
    """Phase 2 wires CPU, memory readers, clock, and snapshot provider."""
    container = build_container(Settings())
    assert container.sampler is None
    assert container.hub is None
    assert isinstance(container.cpu_reader, PsutilCpuReader)
    assert isinstance(container.memory_reader, PsutilMemoryReader)
    assert isinstance(container.clock, SystemClock)
    assert callable(container.snapshot_provider)
    assert isinstance(container.snapshot_provider, CollectSnapshot)
    assert isinstance(container.disk_reader, PsutilDiskReader)
    assert isinstance(container.network_reader, PsutilNetworkReader)
    assert isinstance(container.process_reader, PsutilProcessReader)
    assert container.sensor_reader is None
    assert container.history_store is None


def test_snapshot_provider_wires_the_network_reader(monkeypatch) -> None:
    """Regression: the network reader must be passed into CollectSnapshot.

    A reader can be present on the container and still be dropped by the
    composition root, which made every network group report
    "Network reader not configured" in production while the E2E fixture (which
    wires its own fakes) looked healthy.
    """
    import asyncio

    import monitor.composition as composition
    from monitor.domain.entities import CpuSnapshot, DiskUsage, MemorySnapshot, NetCounters
    from monitor.domain.types import Ok
    from monitor.domain.values import (
        Bytes,
        LoadAverage,
        MonotonicTimestamp,
        Percent,
        SwapUsage,
    )

    calls = {"network": 0}

    class FakeCpuReader:
        async def read(self):
            return Ok(
                CpuSnapshot(
                    cpu_total=Percent(value=10.0),
                    per_core=(Percent(value=10.0),),
                    load_average=LoadAverage(value=0.5),
                    core_count=1,
                    frequency_hz=None,
                )
            )

    class FakeMemoryReader:
        async def read(self):
            return Ok(
                MemorySnapshot(
                    total=Bytes(value=1024),
                    available=Bytes(value=512),
                    used_percent=Percent(value=50.0),
                    swap=SwapUsage(total=Bytes(value=0), used=Bytes(value=0)),
                )
            )

    class FakeDiskReader:
        async def read(self):
            return Ok(
                DiskUsage(
                    device="/",
                    total=Bytes(value=1000),
                    used=Bytes(value=250),
                    percent=Percent(value=25.0),
                )
            )

    class FakeNetworkReader:
        async def read(self):
            calls["network"] += 1
            return Ok(
                NetCounters(
                    rx_bytes=Bytes(value=1200),
                    tx_bytes=Bytes(value=800),
                    sampled_at=MonotonicTimestamp(seconds=1.0),
                )
            )

    monkeypatch.setattr(composition, "PsutilCpuReader", FakeCpuReader)
    monkeypatch.setattr(composition, "PsutilMemoryReader", FakeMemoryReader)
    monkeypatch.setattr(composition, "PsutilDiskReader", FakeDiskReader)
    monkeypatch.setattr(composition, "PsutilNetworkReader", FakeNetworkReader)

    container = composition.build_container(Settings())
    snapshot = asyncio.run(container.snapshot_provider())

    assert calls["network"] == 1
    assert isinstance(snapshot.network, Ok)
    assert snapshot.network.value.rx_bytes.value == 1200
    assert snapshot.network.value.tx_bytes.value == 800
