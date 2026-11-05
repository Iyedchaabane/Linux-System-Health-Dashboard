"""Composition root: wires adapters into use cases.

This is the ONLY place that imports from infrastructure and presentation.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from monitor.application.collect_snapshot import CollectSnapshot
from monitor.application.ports import HistoryStore, Sampler
from monitor.config.settings import Settings
from monitor.domain.ports import (
    Clock,
    CpuReader,
    DiskReader,
    MemoryReader,
    NetReader,
    ProcessReader,
    SensorReader,
)
from monitor.infrastructure.psutil_cpu import PsutilCpuReader
from monitor.infrastructure.psutil_disk import PsutilDiskReader
from monitor.infrastructure.psutil_memory import PsutilMemoryReader
from monitor.infrastructure.psutil_network import PsutilNetworkReader
from monitor.infrastructure.psutil_process import PsutilProcessReader
from monitor.infrastructure.system_clock import SystemClock


class BroadcastHub(Protocol):
    """Protocol for the broadcast hub - implemented by presentation.ws.hub.BroadcastHub."""

    async def connect(
        self,
        client_id: str,
        ip_address: str,
        message_queue_size: int,
    ) -> dict[str, Any] | None:
        """Register a new client connection."""
        ...

    def disconnect(self, client_id: str, reason: str) -> None:
        """Remove a client from the hub."""
        ...

    def publish(self, message: str) -> None:
        """Broadcast a message to all connected clients."""
        ...

    async def close(self) -> None:
        """Close all client connections gracefully."""
        ...


@dataclass(slots=True)
class Container:
    """Application container holding all wired dependencies."""

    settings: Settings
    sampler: Sampler | None = None
    hub: BroadcastHub | None = None
    cpu_reader: CpuReader | None = None
    memory_reader: MemoryReader | None = None
    disk_reader: DiskReader | None = None
    network_reader: NetReader | None = None
    process_reader: ProcessReader | None = None
    sensor_reader: SensorReader | None = None
    clock: Clock | None = None
    history_store: HistoryStore | None = None
    snapshot_provider: Callable[[], Any] | None = None
    cleanup_callback: Callable[[], None] | None = None

    def __post_init__(self) -> None:
        """Validate that required components are wired."""
        pass


def build_container(settings: Settings) -> Container:
    """Build the application container with all dependencies wired.

    Args:
        settings: Validated application settings.

    Returns:
        A Container with all components wired.
    """
    clock = SystemClock()
    cpu_reader = PsutilCpuReader()
    memory_reader = PsutilMemoryReader()

    disk_reader = PsutilDiskReader()
    network_reader = PsutilNetworkReader()
    process_reader = PsutilProcessReader(max_processes=settings.max_processes_in_stream)

    collect_snapshot = CollectSnapshot(
        cpu_reader=cpu_reader,
        memory_reader=memory_reader,
        clock=clock,
        disk_reader=disk_reader,
        network_reader=network_reader,
        process_reader=process_reader,
    )

    return Container(
        settings=settings,
        sampler=None,
        hub=None,
        cpu_reader=cpu_reader,
        memory_reader=memory_reader,
        disk_reader=disk_reader,
        network_reader=network_reader,
        process_reader=process_reader,
        sensor_reader=None,
        clock=clock,
        history_store=None,
        snapshot_provider=collect_snapshot,
        cleanup_callback=process_reader.close,
    )
