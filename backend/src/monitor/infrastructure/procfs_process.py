"""Process collector reading Linux procfs directly, without psutil global state."""

from __future__ import annotations

import os
import time
from pathlib import Path

from monitor.domain.entities import ProcessInfo, ProcessList
from monitor.domain.types import MetricResult, Ok
from monitor.infrastructure.psutil_process import (
    PsutilProcessReader,
    _cpu_percent,
    _CpuSample,
    _sort_key,
    _truncate_name,
)

_CLK_TCK = os.sysconf("SC_CLK_TCK")
_PAGE_SIZE = os.sysconf("SC_PAGE_SIZE")


def _parse_stat(stat_text: str, pid: int) -> tuple[str, int, int] | None:
    """Validate stat and return name, raw starttime ticks and CPU ticks."""
    # comm may contain spaces and parentheses, so use the outer pair.
    lparen = stat_text.find("(")
    rparen = stat_text.rfind(")")
    if lparen < 0 or rparen <= lparen or int(stat_text[:lparen].strip()) != pid:
        raise ValueError("malformed stat")
    name = stat_text[lparen + 1 : rparen]
    if not name:
        return None

    # Fields after comm are 1-based; require through starttime (22).
    rest = stat_text[rparen + 1 :].split()
    if len(rest) < 20:
        raise ValueError("truncated stat")
    if rest[0] == "Z":
        return None
    utime = int(rest[11])
    stime = int(rest[12])
    starttime = int(rest[19])
    if utime < 0 or stime < 0 or starttime < 0:
        raise ValueError("negative stat value")
    return name, starttime, utime + stime


def _parse_process(process_dir: Path, pid: int) -> tuple[str, tuple[int, float], float, int] | None:
    """Parse one identity-checked ``stat``/``statm`` observation.

    Returns ``(name, identity, cpu_seconds, rss_bytes)``; ``None`` for a zombie
    or a process whose ``comm`` is empty. Raises ``OSError``, ``ValueError``,
    ``UnicodeDecodeError`` or ``IndexError`` when the entry disappeared, is
    unreadable or is malformed, so the caller can count it as skipped.
    """
    parsed = _parse_stat((process_dir / "stat").read_text(encoding="utf-8"), pid)
    if parsed is None:
        return None
    name, starttime, cpu_ticks = parsed

    # RSS from resident pages; a missing or malformed statm skips the process
    # instead of reporting a fabricated zero.
    statm = (process_dir / "statm").read_text(encoding="utf-8").split()
    resident_pages = int(statm[1])
    if resident_pages < 0:
        raise ValueError("negative resident pages")

    # Reject mixed observations across PID reuse; compare ticks before float rounding.
    rechecked = _parse_stat((process_dir / "stat").read_text(encoding="utf-8"), pid)
    if rechecked is None or rechecked[1] != starttime:
        raise ValueError("process identity changed")

    identity = (pid, starttime / _CLK_TCK)
    cpu_seconds = cpu_ticks / _CLK_TCK
    return name, identity, cpu_seconds, resident_pages * _PAGE_SIZE


class ProcfsProcessReader(PsutilProcessReader):
    """Top-N process reader parsed from ``/proc`` with CPU-time deltas.

    This reader has the same contract as ``PsutilProcessReader``: it lists only
    pids present in the procfs tree supplied to it (the container's view for
    ``/proc``, the host's view for a mounted host procfs), and rows must never
    be summed into host totals unless that scope is intended. ``name`` is the
    kernel ``comm`` field,
    which the kernel truncates to 15 bytes; ``memory_rss_bytes`` is resident set
    size (RSS), which double-counts shared pages between processes.

    CPU usage uses the same ``(pid, starttime)`` identity and monotonic
    wall-clock delta as the psutil reader, so the first observation of an
    identity reports ``None`` instead of a fabricated zero. The result is
    ``partial`` when a process was skipped or any collected row still lacks a
    CPU delta; the top-N cap alone is not partial.

    The reader never assigns ``psutil.PROCFS_PATH`` and holds no psutil global
    state, so it can point at a host procfs mount (e.g. ``/host/proc``) while
    other collectors keep their own view. Unreadable or malformed per-process
    files are counted in ``skipped``; a missing root is transient and an
    unreadable root is a permission failure, both mapped by the inherited
    blocking wrapper. The single-flight worker lifecycle comes from
    ``PsutilProcessReader``; owners must still call ``close()``.
    """

    def __init__(self, procfs_path: str, max_processes: int = 25) -> None:
        if not procfs_path:
            raise ValueError("procfs_path must not be empty")
        super().__init__(max_processes=max_processes)
        self._procfs_path = procfs_path

    def _collect(self) -> MetricResult[ProcessList]:
        sampled_at = time.monotonic()
        rows: list[ProcessInfo] = []
        current: dict[tuple[int, float], _CpuSample] = {}
        skipped = 0
        root = Path(self._procfs_path)

        # Root errors propagate to _read_blocking for a typed Unavailable.
        with os.scandir(root) as entries:
            pids = sorted(int(entry.name) for entry in entries if entry.name.isdigit())

        for pid in pids:
            try:
                parsed = _parse_process(root / str(pid), pid)
            except (OSError, ValueError, UnicodeDecodeError, IndexError):
                skipped += 1
                continue
            if parsed is None:
                skipped += 1
                continue

            name, identity, cpu_seconds, rss_bytes = parsed
            cpu_percent = _cpu_percent(self._previous.get(identity), cpu_seconds, sampled_at)
            current[identity] = _CpuSample(cpu_seconds=cpu_seconds, sampled_at=sampled_at)
            rows.append(
                ProcessInfo(
                    pid=pid,
                    name=_truncate_name(name),
                    cpu_percent=cpu_percent,
                    memory_rss_bytes=rss_bytes,
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
