"""CollectSnapshot use case: orchestrates collectors and builds SystemSnapshot."""

from __future__ import annotations

import asyncio

from monitor.domain.entities import SystemSnapshot
from monitor.domain.ports import Clock, CpuReader, DiskReader, MemoryReader, NetReader
from monitor.domain.types import Unavailable, UnavailableKind


class CollectSnapshot:
    """Orchestrates CPU, memory, disk and network collection into a SystemSnapshot."""

    def __init__(
        self,
        cpu_reader: CpuReader,
        memory_reader: MemoryReader,
        clock: Clock,
        disk_reader: DiskReader | None = None,
        network_reader: NetReader | None = None,
    ) -> None:
        self._cpu = cpu_reader
        self._memory = memory_reader
        self._disk = disk_reader
        self._network = network_reader
        self._clock = clock

    async def __call__(self) -> SystemSnapshot:
        ts_mono = self._clock.monotonic()
        ts_utc = self._clock.utc()

        cpu_result, memory_result = await asyncio.gather(
            self._cpu.read(),
            self._memory.read(),
        )

        if self._disk is not None:
            disk_result = await self._disk.read()
        else:
            disk_result = Unavailable(UnavailableKind.DISABLED, "Disk reader not configured")

        if self._network is not None:
            network_result = await self._network.read()
        else:
            network_result = Unavailable(UnavailableKind.DISABLED, "Network reader not configured")

        return SystemSnapshot(
            cpu=cpu_result,
            memory=memory_result,
            disk=disk_result,
            network=network_result,
            timestamp_monotonic=ts_mono,
            timestamp_utc=ts_utc,
        )
