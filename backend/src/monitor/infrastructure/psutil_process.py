"""Process collector using psutil on a dedicated single thread."""

from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock

import psutil

from monitor.domain.entities import PROCESS_NAME_MAX_LENGTH, ProcessInfo, ProcessList
from monitor.domain.types import MetricResult, Ok, Unavailable, UnavailableKind

logger = logging.getLogger("monitor.infrastructure.psutil_process")

@dataclass(frozen=True)
class _CpuSample:
    """CPU time consumed and monotonic wall clock captured for one identity."""

    cpu_seconds: float
    sampled_at: float


def _truncate_name(name: str) -> str:
    """Truncate to the wire limit without splitting a surrogate pair."""
    if len(name) <= PROCESS_NAME_MAX_LENGTH:
        return name
    truncated = name[:PROCESS_NAME_MAX_LENGTH]
    if 0xD800 <= ord(truncated[-1]) <= 0xDBFF:
        truncated = truncated[:-1]
    return truncated


def _cpu_percent(
    previous: _CpuSample | None, cpu_seconds: float, sampled_at: float
) -> float | None:
    """Usage from CPU-time and wall-clock deltas; ``None`` without a delta."""
    if previous is None:
        return None
    elapsed = sampled_at - previous.sampled_at
    delta_cpu = cpu_seconds - previous.cpu_seconds
    if elapsed <= 0.0 or delta_cpu < 0.0:
        return None
    return 100.0 * delta_cpu / elapsed


def _sort_key(row: ProcessInfo) -> tuple[int, float, int]:
    """CPU descending with null last, PID ascending for ties."""
    if row.cpu_percent is None:
        return (1, 0.0, row.pid)
    return (0, -row.cpu_percent, row.pid)


class PsutilProcessReader:
    """Top-N process reader using CPU-time deltas between consecutive samples.

    Only processes visible in the current PID namespace are listed: in a
    container this is the container's view, not a host-wide inventory, and the
    rows must never be summed into host totals. ``memory_rss_bytes`` is resident
    set size, which double-counts shared pages between processes.

    CPU usage is computed from the CPU-time delta of the same ``(pid,
    create_time)`` identity over the monotonic wall-clock delta between samples,
    so 100.0 means one fully occupied logical CPU and values above 100 are
    valid. The first observation of an identity, and the first after PID reuse,
    report ``None`` rather than a fabricated zero; no sampling interval is
    slept through. The result is ``partial`` when a process was skipped or when
    any collected row still lacks a CPU delta; the top-N cap alone is not
    partial.

    Each reader owns one lazy worker and admits only one outstanding collection,
    even if its asyncio waiter is cancelled. Abandoned results are not replayed;
    their completed CPU observations remain the baseline for the next collection.
    Owners must call ``close()`` when collection stops. Closing does not wait for
    a running worker and cannot interrupt a stuck system call; Python may still
    wait for that worker when the interpreter exits.
    """

    def __init__(self, max_processes: int = 25) -> None:
        if max_processes < 1:
            raise ValueError("max_processes must be positive")
        self._max_processes = max_processes
        self._previous: dict[tuple[int, float], _CpuSample] = {}
        self._submission_lock = Lock()
        self._executor: ThreadPoolExecutor | None = None
        self._flight: Future[MetricResult[ProcessList]] | None = None
        self._closed = False

    async def read(self) -> MetricResult[ProcessList]:
        # No await between admission and submission. The lock also serializes
        # synchronous close() against callers on other threads/event loops.
        with self._submission_lock:
            if self._closed:
                return Unavailable(
                    UnavailableKind.TRANSIENT, "Process information reader is closed."
                )
            if self._flight is not None and not self._flight.done():
                return Unavailable(
                    UnavailableKind.TRANSIENT, "Process information collection is already running."
                )
            if self._executor is None:
                self._executor = ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="process-collector"
                )
            flight = self._executor.submit(self._read_blocking)
            self._flight = flight

        # Track the concurrent future, not the cancellable asyncio waiter. A
        # completed flight has finished all baseline updates before admission
        # can submit fresh work; never clear the flight in a waiter finally.
        return await asyncio.shield(asyncio.wrap_future(flight))

    def close(self) -> None:
        """Reject new reads and release the executor without waiting for work."""
        with self._submission_lock:
            if self._closed:
                return
            self._closed = True
            executor = self._executor
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)

    def _read_blocking(self) -> MetricResult[ProcessList]:
        try:
            return self._collect()
        except (psutil.AccessDenied, PermissionError):
            logger.debug("Process enumeration access denied")
            return Unavailable(UnavailableKind.PERMISSION, "Process information is not readable.")
        except Exception:
            logger.debug("Process enumeration failed")
            return Unavailable(
                UnavailableKind.TRANSIENT,
                "Process information is temporarily unavailable.",
            )

    def _collect(self) -> MetricResult[ProcessList]:
        sampled_at = time.monotonic()
        rows: list[ProcessInfo] = []
        current: dict[tuple[int, float], _CpuSample] = {}
        skipped = 0

        for cached_process in psutil.process_iter():
            try:
                # Iterator objects cache identity across samples, even after PID
                # reuse. Observe through a local fresh object instead.
                process = psutil.Process(cached_process.pid)
                identity = (process.pid, process.create_time())
                if process.status() == psutil.STATUS_ZOMBIE:
                    skipped += 1
                    continue
                name = process.name()
                # Validate the entire name before truncation can hide a suffix.
                name.encode("utf-8", errors="strict")
                name = _truncate_name(name)
                times = process.cpu_times()
                cpu_seconds = times.user + times.system
                rss = process.memory_info().rss
                # A second fresh object bypasses create_time()'s instance cache
                # and rejects observations spanning a PID replacement.
                if identity != (process.pid, psutil.Process(process.pid).create_time()):
                    skipped += 1
                    continue
            except (
                psutil.NoSuchProcess,
                psutil.ZombieProcess,
                psutil.AccessDenied,
                OSError,
                UnicodeEncodeError,
            ):
                skipped += 1
                continue

            if not name:
                skipped += 1
                continue

            cpu_percent = _cpu_percent(self._previous.get(identity), cpu_seconds, sampled_at)
            current[identity] = _CpuSample(cpu_seconds=cpu_seconds, sampled_at=sampled_at)
            rows.append(
                ProcessInfo(
                    pid=process.pid,
                    name=name,
                    cpu_percent=cpu_percent,
                    memory_rss_bytes=rss,
                )
            )

        # Retain only identities seen now: gone PIDs and reused PIDs are dropped.
        self._previous = current
        rows.sort(key=_sort_key)
        partial = skipped > 0 or any(row.cpu_percent is None for row in rows)
        return Ok(
            ProcessList(items=tuple(rows[: self._max_processes]), skipped=skipped),
            partial=partial,
        )
