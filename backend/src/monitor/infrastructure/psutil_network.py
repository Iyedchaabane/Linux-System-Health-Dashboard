"""Network counter collector using psutil."""

from __future__ import annotations

import asyncio
import logging
import time

import psutil

from monitor.domain.entities import NetCounters
from monitor.domain.types import MetricResult, Ok, Unavailable, UnavailableKind
from monitor.domain.values import Bytes, MonotonicTimestamp

logger = logging.getLogger("monitor.infrastructure.psutil_network")


class PsutilNetworkReader:
    """Network reader collecting cumulative byte counters across all interfaces."""

    def __init__(self) -> None:
        pass

    async def read(self) -> MetricResult[NetCounters]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._read_blocking)

    def _read_blocking(self) -> MetricResult[NetCounters]:
        try:
            stats = psutil.net_io_counters(pernic=True)
            if not stats:
                return Unavailable(UnavailableKind.UNSUPPORTED, "No network interfaces available")

            total_rx = sum(s.bytes_recv for s in stats.values())
            total_tx = sum(s.bytes_sent for s in stats.values())

            return Ok(
                NetCounters(
                    rx_bytes=Bytes(value=total_rx),
                    tx_bytes=Bytes(value=total_tx),
                    sampled_at=MonotonicTimestamp(seconds=time.monotonic()),
                )
            )

        except (psutil.AccessDenied, PermissionError):
            return Unavailable(
                UnavailableKind.PERMISSION,
                "Network metrics require elevated privileges",
            )

        except (OSError, psutil.Error):
            return Unavailable(
                UnavailableKind.TRANSIENT,
                "Network read temporarily failed",
            )
