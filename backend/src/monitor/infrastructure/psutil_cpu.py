"""CPU collector using psutil on a dedicated single thread."""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import psutil

from monitor.domain.entities import CpuSnapshot
from monitor.domain.types import MetricResult, Ok, Unavailable, UnavailableKind
from monitor.domain.values import LoadAverage, Percent

logger = logging.getLogger("monitor.infrastructure.psutil_cpu")

_cpu_executor: ThreadPoolExecutor | None = None


def _get_cpu_executor() -> ThreadPoolExecutor:
    global _cpu_executor
    if _cpu_executor is None:
        _cpu_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cpu-collector")
    return _cpu_executor


class PsutilCpuReader:
    """CPU reader using psutil on a dedicated single thread."""

    def __init__(self) -> None:
        executor = _get_cpu_executor()
        executor.submit(psutil.cpu_percent, percpu=True, interval=None).result()

    async def read(self) -> MetricResult[CpuSnapshot]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_get_cpu_executor(), self._read_blocking)

    def _read_blocking(self) -> MetricResult[CpuSnapshot]:
        try:
            per_core_raw = psutil.cpu_percent(percpu=True, interval=None)
            if not per_core_raw:
                return Unavailable(UnavailableKind.UNSUPPORTED, "No CPU cores detected")

            core_count = psutil.cpu_count(logical=True)
            if core_count is None or core_count < 1:
                return Unavailable(UnavailableKind.UNSUPPORTED, "CPU core count unavailable")
            if len(per_core_raw) != core_count:
                return Unavailable(UnavailableKind.UNSUPPORTED, "CPU core count mismatch")

            per_core = tuple(Percent(value=p) for p in per_core_raw)
            cpu_total = Percent(value=sum(per_core_raw) / len(per_core_raw))

            # Frequency: optional, local error handling for all expected exceptions
            freq_hz: float | None = None
            _freq_exceptions = (
                AttributeError,
                OSError,
                psutil.AccessDenied,
                PermissionError,
                psutil.Error,
            )
            try:
                freq = psutil.cpu_freq()
                if freq is not None and freq.current is not None and freq.current > 0:
                    freq_hz = freq.current * 1_000_000
            except _freq_exceptions as e:
                logger.debug("CPU frequency unavailable", extra={"error": str(e)})

            # Load average: required
            try:
                load_1m = os.getloadavg()[0]
            except OSError as e:
                logger.debug("Load average unavailable", extra={"error": str(e)})
                return Unavailable(UnavailableKind.UNSUPPORTED, "Load average unavailable")

            return Ok(
                CpuSnapshot(
                    cpu_total=cpu_total,
                    per_core=per_core,
                    load_average=LoadAverage(value=load_1m),
                    core_count=core_count,
                    frequency_hz=freq_hz,
                )
            )

        except (psutil.AccessDenied, PermissionError):
            logger.debug("CPU access denied", extra={"error": "AccessDenied"})
            return Unavailable(
                UnavailableKind.PERMISSION,
                "CPU metrics require elevated privileges",
            )

        except (psutil.NoSuchProcess, psutil.Error) as e:
            logger.debug("CPU read failed", extra={"error": type(e).__name__})
            return Unavailable(
                UnavailableKind.TRANSIENT,
                "CPU read temporarily failed",
            )
