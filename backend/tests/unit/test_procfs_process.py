"""Unit tests for the procfs process collector.

Every test builds a temporary fake ``/proc`` tree, so parsing, skipping and
delta math are exact and never read the host's process inventory. The
collector's module clock is replaced; no test sleeps.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import psutil
import pytest

import monitor.infrastructure.procfs_process as procfs_module
from monitor.domain.types import Ok, Unavailable, UnavailableKind
from monitor.infrastructure.procfs_process import (
    _CLK_TCK,
    _PAGE_SIZE,
    ProcfsProcessReader,
)

requires_unprivileged = pytest.mark.skipif(
    os.geteuid() == 0, reason="root bypasses chmod-based permission checks"
)


@pytest.fixture(autouse=True)
def close_readers(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Every reader releases its owned worker, including assertion failures."""
    readers: list[ProcfsProcessReader] = []
    original_init = ProcfsProcessReader.__init__

    def initialize(self: ProcfsProcessReader, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        readers.append(self)

    monkeypatch.setattr(ProcfsProcessReader, "__init__", initialize)
    try:
        yield
    finally:
        for reader in readers:
            reader.close()


class FakeMonotonic:
    """Controllable monotonic clock for the collector module."""

    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def monotonic(self) -> float:
        return self.now


def _use_clock(monkeypatch: pytest.MonkeyPatch, clock: FakeMonotonic) -> None:
    """Replace the collector module's clock without touching the global one."""
    monkeypatch.setattr(procfs_module, "time", SimpleNamespace(monotonic=clock.monotonic))


def _stat(
    pid: int,
    name: str = "proc",
    *,
    state: str = "S",
    utime: int = 0,
    stime: int = 0,
    starttime: int = 1,
) -> str:
    """Build a 22-field ``stat`` line with only the parsed fields non-zero."""
    fields = ["0"] * 22
    fields[0] = str(pid)  # field 1
    fields[1] = f"({name})"  # field 2, comm
    fields[2] = state  # field 3
    fields[13] = str(utime)  # field 14
    fields[14] = str(stime)  # field 15
    fields[21] = str(starttime)  # field 22
    return " ".join(fields) + "\n"


def _replace_field(stat_text: str, index: int, value: str) -> str:
    """Replace one whitespace-separated 0-based field of a simple stat line."""
    fields = stat_text.split()
    fields[index] = value
    return " ".join(fields)


def _create(
    root: Path,
    pid: int,
    *,
    name: str = "proc",
    state: str = "S",
    utime: int = 0,
    stime: int = 0,
    starttime: int = 1,
    pages: int = 1,
    stat_text: str | None = None,
    raw_stat: bytes | None = None,
    statm_text: str | None = None,
    write_stat: bool = True,
    write_statm: bool = True,
) -> Path:
    """Create one fake process directory with ``stat``/``statm`` files."""
    process_dir = root / str(pid)
    process_dir.mkdir(parents=True, exist_ok=True)
    if write_stat:
        if raw_stat is not None:
            (process_dir / "stat").write_bytes(raw_stat)
        else:
            text = (
                stat_text
                if stat_text is not None
                else _stat(pid, name, state=state, utime=utime, stime=stime, starttime=starttime)
            )
            (process_dir / "stat").write_text(text, encoding="utf-8")
    if write_statm:
        text = statm_text if statm_text is not None else f"0 {pages} 0 0 0 0 0\n"
        (process_dir / "statm").write_text(text, encoding="utf-8")
    return process_dir


def _write_stat(
    root: Path,
    pid: int,
    *,
    name: str = "proc",
    state: str = "S",
    utime: int = 0,
    stime: int = 0,
    starttime: int = 1,
) -> None:
    """Rewrite just the ``stat`` file for a later sample."""
    (root / str(pid) / "stat").write_text(
        _stat(pid, name, state=state, utime=utime, stime=stime, starttime=starttime),
        encoding="utf-8",
    )


async def test_first_sample_reports_no_cpu_delta_and_is_partial(tmp_path: Path) -> None:
    """A fresh reader has no baseline, so CPU is None (never a fake zero)."""
    _create(tmp_path, 2, name="beta", pages=3)
    _create(tmp_path, 1, name="alpha", pages=2)

    result = await ProcfsProcessReader(str(tmp_path)).read()

    assert isinstance(result, Ok)
    assert result.partial is True
    assert result.value.skipped == 0
    assert [row.pid for row in result.value.items] == [1, 2]
    assert [row.name for row in result.value.items] == ["alpha", "beta"]
    assert [row.cpu_percent for row in result.value.items] == [None, None]
    assert [row.memory_rss_bytes for row in result.value.items] == [
        2 * _PAGE_SIZE,
        3 * _PAGE_SIZE,
    ]


async def test_second_sample_computes_cpu_delta_and_orders_by_cpu(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """CPU time over monotonic time yields exact percentages, highest first."""
    clock = FakeMonotonic()
    _use_clock(monkeypatch, clock)
    _create(tmp_path, 1, name="one")
    _create(tmp_path, 2, name="two")
    reader = ProcfsProcessReader(str(tmp_path))

    first = await reader.read()
    assert isinstance(first, Ok)

    clock.now = 101.0
    half = _CLK_TCK // 2
    tenth = _CLK_TCK // 10
    _write_stat(tmp_path, 1, name="one", utime=tenth)
    _write_stat(tmp_path, 2, name="two", utime=half)
    result = await reader.read()

    assert isinstance(result, Ok)
    assert result.partial is False
    assert [row.pid for row in result.value.items] == [2, 1]
    assert result.value.items[0].cpu_percent == pytest.approx(100.0 * half / _CLK_TCK)
    assert result.value.items[1].cpu_percent == pytest.approx(100.0 * tenth / _CLK_TCK)


@pytest.mark.parametrize("name", ["my proc", "na)me (x", "(weird)"])
async def test_comm_with_spaces_and_parentheses_is_preserved(tmp_path: Path, name: str) -> None:
    """comm is taken between the outer parentheses, not split on spaces."""
    _create(tmp_path, 1, name=name)

    result = await ProcfsProcessReader(str(tmp_path)).read()

    assert isinstance(result, Ok)
    assert [row.name for row in result.value.items] == [name]


@pytest.mark.parametrize(
    "stat_text",
    [
        "1 proc S 0 0",
        _replace_field(_stat(1), 13, "x"),
        _replace_field(_stat(1), 13, "-1"),
        " ".join(_stat(1).split()[:10]),
    ],
    ids=["no_parentheses", "non_numeric_utime", "negative_utime", "truncated"],
)
async def test_malformed_stat_is_skipped_not_listed(tmp_path: Path, stat_text: str) -> None:
    """Malformed entries are counted as skipped, never fabricated rows."""
    _create(tmp_path, 1, stat_text=stat_text)

    result = await ProcfsProcessReader(str(tmp_path)).read()

    assert isinstance(result, Ok)
    assert result.value.items == ()
    assert result.value.skipped == 1
    assert result.partial is True


@pytest.mark.parametrize(
    "statm_text",
    ["0 x 0 0 0 0 0", "0"],
    ids=["non_numeric_resident", "truncated"],
)
async def test_malformed_statm_is_skipped_not_listed(tmp_path: Path, statm_text: str) -> None:
    """Malformed statm skips the process instead of reporting rss zero."""
    _create(tmp_path, 1, statm_text=statm_text)

    result = await ProcfsProcessReader(str(tmp_path)).read()

    assert isinstance(result, Ok)
    assert result.value.items == ()
    assert result.value.skipped == 1
    assert result.partial is True


async def test_stat_pid_mismatch_is_skipped(tmp_path: Path) -> None:
    """A stat line for another pid must not become a row for this directory."""
    _create(tmp_path, 1, stat_text=_replace_field(_stat(1), 0, "2"))

    result = await ProcfsProcessReader(str(tmp_path)).read()

    assert isinstance(result, Ok)
    assert result.value.items == ()
    assert result.value.skipped == 1


@pytest.mark.parametrize(
    ("write_stat", "write_statm"),
    [(False, True), (True, False)],
    ids=["missing_stat", "missing_statm"],
)
async def test_missing_process_files_are_skipped(
    tmp_path: Path, write_stat: bool, write_statm: bool
) -> None:
    """A missing stat or statm skips the process instead of reporting zero."""
    _create(tmp_path, 1, write_stat=write_stat, write_statm=write_statm)

    result = await ProcfsProcessReader(str(tmp_path)).read()

    assert isinstance(result, Ok)
    assert result.value.items == ()
    assert result.value.skipped == 1


async def test_zombie_process_is_skipped(tmp_path: Path) -> None:
    """Zombies have no meaningful CPU or RSS and are not listed."""
    _create(tmp_path, 1, state="Z")

    result = await ProcfsProcessReader(str(tmp_path)).read()

    assert isinstance(result, Ok)
    assert result.value.items == ()
    assert result.value.skipped == 1


async def test_invalid_utf8_comm_is_skipped(tmp_path: Path) -> None:
    """A non-UTF-8 stat line is skipped, not decoded with a replacement."""
    _create(tmp_path, 1, raw_stat=b"1 (bad\xff) S " + b"0 " * 20)

    result = await ProcfsProcessReader(str(tmp_path)).read()

    assert isinstance(result, Ok)
    assert result.value.items == ()
    assert result.value.skipped == 1


async def test_non_numeric_root_entries_are_ignored(tmp_path: Path) -> None:
    """Only numeric directory names are treated as pids."""
    (tmp_path / "self").write_text("not a pid\n", encoding="utf-8")
    (tmp_path / "12abc").mkdir()
    _create(tmp_path, 1, name="real")

    result = await ProcfsProcessReader(str(tmp_path)).read()

    assert isinstance(result, Ok)
    assert [row.pid for row in result.value.items] == [1]
    assert result.value.skipped == 0


async def test_empty_root_is_ok_and_not_partial(tmp_path: Path) -> None:
    """An empty procfs is a valid empty list, not an unavailable metric."""
    result = await ProcfsProcessReader(str(tmp_path)).read()

    assert isinstance(result, Ok)
    assert result.value.items == ()
    assert result.value.skipped == 0
    assert result.partial is False


async def test_missing_root_is_transient(tmp_path: Path) -> None:
    """A disappeared procfs root is a transient failure."""
    result = await ProcfsProcessReader(str(tmp_path / "missing")).read()

    assert isinstance(result, Unavailable)
    assert result.kind is UnavailableKind.TRANSIENT


@requires_unprivileged
async def test_unreadable_root_maps_to_permission(tmp_path: Path) -> None:
    """An unreadable procfs root is a permission failure."""
    root = tmp_path / "proc"
    root.mkdir()
    root.chmod(0o000)
    try:
        result = await ProcfsProcessReader(str(root)).read()
    finally:
        root.chmod(0o755)

    assert isinstance(result, Unavailable)
    assert result.kind is UnavailableKind.PERMISSION


@requires_unprivileged
async def test_unreadable_process_stat_is_skipped(tmp_path: Path) -> None:
    """An unreadable per-process stat skips that process only."""
    process_dir = _create(tmp_path, 1)
    (process_dir / "stat").chmod(0o000)
    try:
        result = await ProcfsProcessReader(str(tmp_path)).read()
    finally:
        (process_dir / "stat").chmod(0o644)

    assert isinstance(result, Ok)
    assert result.value.items == ()
    assert result.value.skipped == 1


async def test_pid_reuse_reports_none_and_replaces_the_baseline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The same pid with a new starttime is a new identity without a baseline."""
    clock = FakeMonotonic()
    _use_clock(monkeypatch, clock)
    _create(tmp_path, 500, starttime=100)
    reader = ProcfsProcessReader(str(tmp_path))

    first = await reader.read()
    assert isinstance(first, Ok)
    assert first.value.items[0].cpu_percent is None

    clock.now = 101.0
    _write_stat(tmp_path, 500, utime=_CLK_TCK, starttime=200)
    second = await reader.read()

    assert isinstance(second, Ok)
    assert second.value.items[0].cpu_percent is None
    assert set(reader._previous) == {(500, 200 / _CLK_TCK)}


@pytest.mark.parametrize(
    "failure",
    [
        "replacement",
        "rounded_identity",
        "pid_mismatch",
        "disappeared",
        "denied",
        "no_parentheses",
        "truncated",
        "invalid_starttime",
        "negative_starttime",
        "invalid_utf8",
    ],
)
async def test_statm_identity_race_is_skipped_and_baseline_is_dropped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str
) -> None:
    """Reject mixed observations; even the same identity must prime after a skip."""
    clock = FakeMonotonic()
    _use_clock(monkeypatch, clock)
    # Adjacent large raw tick counts round to the same float seconds.
    starttime = 2**60 if failure == "rounded_identity" else 100
    process_dir = _create(tmp_path, 1, name="old (proc)", starttime=starttime)
    _create(tmp_path, 2, name="intact", pages=3)
    reader = ProcfsProcessReader(str(tmp_path))
    await reader.read()

    clock.now = 101.0
    _write_stat(tmp_path, 1, name="old (proc)", utime=_CLK_TCK, starttime=starttime)
    replacement = failure in {"replacement", "rounded_identity"}
    recovered_starttime = starttime + 1 if replacement else starttime
    original_read = Path.read_text
    armed = True
    deny_recheck = False
    statm_reads = 0

    def racing_read(path: Path, *args: Any, **kwargs: Any) -> str:
        nonlocal armed, deny_recheck, statm_reads
        if path == process_dir / "stat" and deny_recheck:
            raise PermissionError("synthetic recheck denial")
        if path == process_dir / "statm":
            statm_reads += 1
            if armed:
                armed = False
                _create(
                    tmp_path,
                    1,
                    name="new )proc(",
                    utime=10 * _CLK_TCK,
                    starttime=recovered_starttime,
                    pages=7,
                )
                stat_path = process_dir / "stat"
                if failure == "pid_mismatch":
                    stat_path.write_text(_stat(99, starttime=starttime), encoding="utf-8")
                elif failure == "disappeared":
                    stat_path.unlink()
                elif failure == "denied":
                    deny_recheck = True
                elif failure == "no_parentheses":
                    stat_path.write_text("1 proc S 0 0", encoding="utf-8")
                elif failure == "truncated":
                    stat_path.write_text("1 (proc) S 0", encoding="utf-8")
                elif failure in {"invalid_starttime", "negative_starttime"}:
                    value = "x" if failure == "invalid_starttime" else "-1"
                    stat_path.write_text(_replace_field(_stat(1), 21, value), encoding="utf-8")
                elif failure == "invalid_utf8":
                    stat_path.write_bytes(b"1 (bad\xff) S " + b"0 " * 20)
        return original_read(path, *args, **kwargs)

    with monkeypatch.context() as race:
        race.setattr(Path, "read_text", racing_read)
        rejected = await reader.read()

    assert isinstance(rejected, Ok)
    assert rejected.partial is True
    assert rejected.value.skipped == 1
    assert [row.pid for row in rejected.value.items] == [2]
    intact = rejected.value.items[0]
    assert (intact.name, intact.memory_rss_bytes, intact.cpu_percent) == (
        "intact",
        3 * _PAGE_SIZE,
        0.0,
    )
    assert set(reader._previous) == {(2, 1 / _CLK_TCK)}
    assert statm_reads == 1

    clock.now = 102.0
    _write_stat(tmp_path, 1, name="new )proc(", utime=10 * _CLK_TCK, starttime=recovered_starttime)
    recovered = await reader.read()
    assert isinstance(recovered, Ok)
    assert recovered.partial is True
    assert recovered.value.skipped == 0
    row = next(row for row in recovered.value.items if row.pid == 1)
    assert (row.name, row.memory_rss_bytes, row.cpu_percent) == (
        "new )proc(",
        7 * _PAGE_SIZE,
        None,
    )

    clock.now = 103.0
    _write_stat(tmp_path, 1, name="new )proc(", utime=11 * _CLK_TCK, starttime=recovered_starttime)
    final = await reader.read()
    assert isinstance(final, Ok)
    assert final.partial is False
    assert final.value.skipped == 0
    assert next(row for row in final.value.items if row.pid == 1).cpu_percent == pytest.approx(
        100.0
    )


async def test_top_n_cap_keeps_the_highest_cpu_rows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The cap truncates rows without making the result partial."""
    clock = FakeMonotonic()
    _use_clock(monkeypatch, clock)
    for pid in range(1, 31):
        _create(tmp_path, pid)
    reader = ProcfsProcessReader(str(tmp_path))

    await reader.read()

    clock.now = 101.0
    for pid in range(1, 31):
        _write_stat(tmp_path, pid, utime=pid * _CLK_TCK)
    result = await reader.read()

    assert isinstance(result, Ok)
    assert len(result.value.items) == 25
    assert [row.pid for row in result.value.items] == list(range(30, 5, -1))
    assert result.value.skipped == 0
    assert result.partial is False


async def test_closed_reader_reports_transient(tmp_path: Path) -> None:
    """close() is permanent for this reader and read() then fails transiently."""
    reader = ProcfsProcessReader(str(tmp_path))
    reader.close()

    result = await reader.read()

    assert isinstance(result, Unavailable)
    assert result.kind is UnavailableKind.TRANSIENT


async def test_reader_does_not_mutate_the_psutil_procfs_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The host procfs reader keeps psutil's own view untouched."""
    monkeypatch.setattr(psutil, "PROCFS_PATH", "/proc")
    _create(tmp_path, 1)

    await ProcfsProcessReader(str(tmp_path)).read()

    assert psutil.PROCFS_PATH == "/proc"


async def test_cap_counts_valid_pids_before_truncation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``total`` counts valid PIDs before the cap and a pure cap is not partial."""
    clock = FakeMonotonic()
    _use_clock(monkeypatch, clock)
    for pid in (1, 2, 3, 4):
        _create(tmp_path, pid, name=f"p{pid}")
    reader = ProcfsProcessReader(str(tmp_path), max_processes=2)
    await reader.read()

    clock.now = 101.0
    for pid in (1, 2, 3, 4):
        _write_stat(tmp_path, pid, name=f"p{pid}", utime=_CLK_TCK)
    capped = await reader.read()

    assert isinstance(capped, Ok)
    assert capped.value.total == 4
    assert capped.value.total > len(capped.value.items)
    assert len(capped.value.items) == 2
    assert capped.value.skipped == 0
    assert capped.partial is False

    bad = tmp_path / "99"
    bad.mkdir()
    (bad / "stat").write_text("not a stat line", encoding="utf-8")
    clock.now = 102.0
    for pid in (1, 2, 3, 4):
        _write_stat(tmp_path, pid, name=f"p{pid}", utime=2 * _CLK_TCK)
    result = await reader.read()

    assert isinstance(result, Ok)
    assert result.value.total == 4
    assert len(result.value.items) == 2
    assert result.value.skipped == 1
