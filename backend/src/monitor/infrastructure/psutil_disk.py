"""Disk (filesystem) collector using psutil."""

from __future__ import annotations

import asyncio
import logging

import psutil

from monitor.domain.entities import DiskUsage
from monitor.domain.types import MetricResult, Ok, Unavailable, UnavailableKind
from monitor.domain.values import Bytes, Percent

logger = logging.getLogger("monitor.infrastructure.psutil_disk")


class PsutilDiskReader:
    """Disk usage reader using psutil for the root filesystem."""

    def __init__(self, *, path: str = "/") -> None:
        self._path = path

    async def read(self) -> MetricResult[DiskUsage]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._read_blocking)

    def _read_blocking(self) -> MetricResult[DiskUsage]:
        try:
            disk = psutil.disk_usage(self._path)
            if disk.total <= 0:
                return Unavailable(
                    UnavailableKind.UNSUPPORTED,
                    f"Disk total unavailable on {self._path}",
                )

            return Ok(
                DiskUsage(
                    device=self._path,
                    total=Bytes(value=disk.total),
                    used=Bytes(value=disk.used),
                    percent=Percent(value=disk.percent),
                )
            )

        except (psutil.AccessDenied, PermissionError):
            logger.debug("Disk access denied", extra={"path": self._path})
            return Unavailable(
                UnavailableKind.PERMISSION,
                f"Disk metrics require elevated privileges on {self._path}",
            )

        except (OSError, psutil.Error) as e:
            logger.debug("Disk read failed", extra={"error": type(e).__name__})
            return Unavailable(
                UnavailableKind.TRANSIENT,
                f"Disk read temporarily failed on {self._path}",
            )
