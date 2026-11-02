"""Unit tests for the composition root container."""

from monitor.application.collect_snapshot import CollectSnapshot
from monitor.composition import Container, build_container
from monitor.config import Settings
from monitor.infrastructure.psutil_cpu import PsutilCpuReader
from monitor.infrastructure.psutil_disk import PsutilDiskReader
from monitor.infrastructure.psutil_memory import PsutilMemoryReader
from monitor.infrastructure.psutil_network import PsutilNetworkReader
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
    assert container.process_reader is None
    assert container.sensor_reader is None
    assert container.history_store is None
