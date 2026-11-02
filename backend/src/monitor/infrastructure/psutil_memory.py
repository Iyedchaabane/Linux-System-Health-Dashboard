"""Memory collector using psutil."""

from __future__ import annotations

import asyncio
import logging

import psutil

from monitor.domain.entities import MemorySnapshot
from monitor.domain.types import MetricResult, Ok, Unavailable, UnavailableKind
from monitor.domain.values import Bytes, Percent, SwapUsage

logger = logging.getLogger("monitor.infrastructure.psutil_memory")


class PsutilMemoryReader:
    """Memory reader using psutil."""

    async def read(self) -> MetricResult[MemorySnapshot]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._read_blocking)

    def _read_blocking(self) -> MetricResult[MemorySnapshot]:
        try:
            vm = psutil.virtual_memory()
            if vm.total <= 0:
                return Unavailable(UnavailableKind.UNSUPPORTED, "Memory total unavailable")

            total = Bytes(value=vm.total)
            available = Bytes(value=vm.available)
            used_percent = Percent(value=((vm.total - vm.available) / vm.total) * 100.0)

            swap = psutil.swap_memory()
            swap_total = Bytes(value=swap.total)
            swap_used = Bytes(value=swap.used)
            swap_usage = SwapUsage(total=swap_total, used=swap_used)

            return Ok(
                MemorySnapshot(
                    total=total,
                    available=available,
                    used_percent=used_percent,
                    swap=swap_usage,
                )
            )

        except (psutil.AccessDenied, PermissionError):
            logger.debug("Memory access denied", extra={"error": "AccessDenied"})
            return Unavailable(
                UnavailableKind.PERMISSION,
                "Memory metrics require elevated privileges",
            )

        except (psutil.NoSuchProcess, psutil.Error) as e:
            logger.debug("Memory read failed", extra={"error": type(e).__name__})
            return Unavailable(
                UnavailableKind.TRANSIENT,
                "Memory read temporarily failed",
            )
