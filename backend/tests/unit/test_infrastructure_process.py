"""Unit tests for the psutil process collector.

``psutil.process_iter`` and the collector's module clock are replaced so every
delta is exact: no test sleeps, reads the host's CPU load or depends on the
machine's process inventory.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import psutil
import pytest

import monitor.infrastructure.psutil_process as process_module
from monitor.domain.entities import PROCESS_NAME_MAX_LENGTH
from monitor.domain.types import Ok, Unavailable, UnavailableKind
from monitor.infrastructure.psutil_process import PsutilProcessReader


@pytest.fixture(autouse=True)
def close_readers(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Every reader releases its owned worker, including assertion failures."""
    readers: list[PsutilProcessReader] = []
    original_init = PsutilProcessReader.__init__

    def initialize(self: PsutilProcessReader, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        readers.append(self)

    monkeypatch.setattr(PsutilProcessReader, "__init__", initialize)
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


@dataclass
class FakeProcess:
    """Minimal psutil.Process stand-in with one optional failure."""

    pid: int
    name_value: str = "proc"
    create_time_value: float = 1.0
    cpu_user: float = 0.0
    cpu_system: float = 0.0
    rss: int = 1024
    status_value: str = psutil.STATUS_RUNNING
    raises: BaseException | None = None

    def _maybe_raise(self) -> None:
        if self.raises is not None:
            raise self.raises

    def status(self) -> str:
        self._maybe_raise()
        return self.status_value

    def create_time(self) -> float:
        self._maybe_raise()
        return self.create_time_value

    def name(self) -> str:
        self._maybe_raise()
        return self.name_value

    def cpu_times(self) -> Any:
        self._maybe_raise()
        return SimpleNamespace(user=self.cpu_user, system=self.cpu_system)

    def memory_info(self) -> Any:
        self._maybe_raise()
        return SimpleNamespace(rss=self.rss)


def _use_clock(monkeypatch: pytest.MonkeyPatch, clock: FakeMonotonic) -> None:
    """Replace the collector module's clock without touching the global one."""
    monkeypatch.setattr(process_module, "time", SimpleNamespace(monotonic=clock.monotonic))


def _use_processes(
    monkeypatch: pytest.MonkeyPatch, processes: list[FakeProcess]
) -> None:
    monkeypatch.setattr(psutil, "process_iter", lambda: list(processes))
    by_pid = {process.pid: process for process in processes}
    monkeypatch.setattr(psutil, "Process", lambda pid: by_pid[pid])


def _process(pid: int, **kwargs: Any) -> FakeProcess:
    return FakeProcess(pid=pid, **kwargs)


def test_reader_rejects_a_non_positive_cap() -> None:
    """The bounded top-N cap must be positive."""
    with pytest.raises(ValueError):
        PsutilProcessReader(max_processes=0)


async def test_first_sample_reports_no_cpu_delta_and_is_partial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh reader has no baseline, so CPU is None (never a fake zero)."""
    clock = FakeMonotonic()
    _use_clock(monkeypatch, clock)
    _use_processes(monkeypatch, [_process(2, cpu_user=5.0), _process(1, cpu_user=1.0)])

    result = await PsutilProcessReader().read()

    assert isinstance(result, Ok)
    assert result.partial is True
    assert result.value.skipped == 0
    assert [row.pid for row in result.value.items] == [1, 2]
    assert [row.cpu_percent for row in result.value.items] == [None, None]


async def test_cpu_percent_uses_cpu_time_and_monotonic_deltas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deltas are exact: +0.5s/1s=50, +2s/1s=200, zero=0, negative and no time= None."""
    clock = FakeMonotonic()
    processes = [_process(pid) for pid in (10, 11, 12, 13)]
    _use_clock(monkeypatch, clock)
    _use_processes(monkeypatch, processes)
    reader = PsutilProcessReader()
    await reader.read()

    clock.now = 101.0
    processes[0].cpu_user = 0.5
    processes[1].cpu_user = 2.0
    processes[2].cpu_user = 0.0
    processes[3].cpu_user = -1.0
    result = await reader.read()

    assert isinstance(result, Ok)
    assert {row.pid: row.cpu_percent for row in result.value.items} == {
        10: 50.0,
        11: 200.0,
        12: 0.0,
        13: None,
    }
    # A value above one full CPU is valid and must not be clamped.
    assert next(row for row in result.value.items if row.pid == 11).cpu_percent == 200.0


@pytest.mark.parametrize("second_time", [100.0, 99.0])
async def test_non_positive_elapsed_reports_none(
    monkeypatch: pytest.MonkeyPatch, second_time: float
) -> None:
    """A zero or backwards clock step cannot produce a CPU percentage."""
    clock = FakeMonotonic(100.0)
    process = _process(1)
    _use_clock(monkeypatch, clock)
    _use_processes(monkeypatch, [process])
    reader = PsutilProcessReader()
    await reader.read()

    clock.now = second_time
    process.cpu_user = 1.0
    result = await reader.read()

    assert isinstance(result, Ok)
    assert result.value.items[0].cpu_percent is None


async def test_pid_reuse_reports_none_and_drops_the_stale_baseline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same pid with a new create_time is a new identity without a baseline."""
    clock = FakeMonotonic()
    process = _process(500, cpu_user=10.0, create_time_value=1.0)
    _use_clock(monkeypatch, clock)
    _use_processes(monkeypatch, [process])
    reader = PsutilProcessReader()

    first = await reader.read()
    assert isinstance(first, Ok)
    assert first.value.items[0].cpu_percent is None

    clock.now = 101.0
    process.create_time_value = 2.0
    process.cpu_user = 50.0
    second = await reader.read()

    assert isinstance(second, Ok)
    assert second.value.items[0].cpu_percent is None
    # The stale (pid, create_time) baseline is not reused nor retained.
    assert set(reader._previous) == {(500, 2.0)}


async def test_retained_baselines_only_cover_the_current_sample(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Baselines shrink for disappeared pids and grow for new identities."""
    clock = FakeMonotonic()
    processes = [_process(pid) for pid in (1, 2, 3)]
    _use_clock(monkeypatch, clock)
    _use_processes(monkeypatch, processes)
    reader = PsutilProcessReader()

    await reader.read()
    assert len(reader._previous) == 3

    clock.now = 101.0
    _use_processes(monkeypatch, processes[:1])
    await reader.read()
    assert len(reader._previous) == 1

    clock.now = 102.0
    _use_processes(monkeypatch, [processes[0], _process(4)])
    await reader.read()
    assert set(reader._previous) == {(1, 1.0), (4, 1.0)}


@pytest.mark.parametrize(
    "process",
    [
        _process(1, raises=psutil.NoSuchProcess(pid=1)),
        _process(1, raises=psutil.ZombieProcess(pid=1)),
        _process(1, raises=psutil.AccessDenied(pid=1)),
        _process(1, raises=OSError("read failed")),
        _process(1, status_value=psutil.STATUS_ZOMBIE),
        _process(1, name_value=""),
    ],
    ids=["no_such_process", "zombie_process", "access_denied", "os_error", "zombie_status", "empty_name"],
)
async def test_unreadable_process_is_skipped_not_listed(
    monkeypatch: pytest.MonkeyPatch, process: FakeProcess
) -> None:
    """Disappeared, zombie and unreadable processes are skipped, never rows."""
    clock = FakeMonotonic()
    _use_clock(monkeypatch, clock)
    _use_processes(monkeypatch, [process])

    result = await PsutilProcessReader().read()

    assert isinstance(result, Ok)
    assert result.value.items == ()
    assert result.value.skipped == 1
    assert result.partial is True


async def test_enumeration_access_denied_maps_to_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enumeration denial is a permission result with the static safe reason."""
    _use_clock(monkeypatch, FakeMonotonic())

    def deny() -> list[FakeProcess]:
        raise psutil.AccessDenied(pid=None)

    monkeypatch.setattr(psutil, "process_iter", deny)

    result = await PsutilProcessReader().read()

    assert isinstance(result, Unavailable)
    assert result.kind == UnavailableKind.PERMISSION
    assert result.reason == "Process information is not readable."


async def test_enumeration_failure_maps_to_transient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Any other enumeration failure is transient, and read() returns it."""
    _use_clock(monkeypatch, FakeMonotonic())

    def fail() -> list[FakeProcess]:
        raise RuntimeError("procfs is broken")

    monkeypatch.setattr(psutil, "process_iter", fail)

    result = await PsutilProcessReader().read()

    assert isinstance(result, Unavailable)
    assert result.kind == UnavailableKind.TRANSIENT
    assert result.reason == "Process information is temporarily unavailable."


async def test_empty_process_list_is_ok_and_not_partial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty namespace is a valid, complete result with no skipped rows."""
    _use_clock(monkeypatch, FakeMonotonic())
    _use_processes(monkeypatch, [])

    result = await PsutilProcessReader().read()

    assert isinstance(result, Ok)
    assert result.value.items == ()
    assert result.value.skipped == 0
    assert result.partial is False


async def test_rows_are_ordered_by_cpu_desc_then_pid_with_nulls_last(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ordering is CPU descending, null last, pid ascending for ties."""
    clock = FakeMonotonic()
    processes = [_process(pid) for pid in (1, 2, 3, 4, 5)]
    _use_clock(monkeypatch, clock)
    _use_processes(monkeypatch, processes)
    reader = PsutilProcessReader()
    await reader.read()

    clock.now = 101.0
    for process, cpu_user in zip(processes, [0.2, 2.0, 0.2, 0.0, -1.0], strict=True):
        process.cpu_user = cpu_user
    result = await reader.read()

    assert isinstance(result, Ok)
    assert [row.pid for row in result.value.items] == [2, 1, 3, 4, 5]
    assert [row.cpu_percent for row in result.value.items] == [200.0, 20.0, 20.0, 0.0, None]


async def test_cap_keeps_top_cpu_rows_and_is_not_partial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The top-N cap alone is not a partial result."""
    clock = FakeMonotonic()
    processes = [_process(pid) for pid in range(1, 31)]
    _use_clock(monkeypatch, clock)
    _use_processes(monkeypatch, processes)
    reader = PsutilProcessReader(max_processes=25)
    await reader.read()

    clock.now = 101.0
    for index, process in enumerate(processes):
        process.cpu_user = (index + 1) / 100.0
    result = await reader.read()

    assert isinstance(result, Ok)
    assert result.partial is False
    assert len(result.value.items) == 25
    assert [row.pid for row in result.value.items] == list(range(30, 5, -1))


@pytest.mark.parametrize(
    ("name", "expected_length"),
    [
        ("a" * 200, PROCESS_NAME_MAX_LENGTH),
        ("é🛠" * 100, PROCESS_NAME_MAX_LENGTH),
        ("a" * PROCESS_NAME_MAX_LENGTH, PROCESS_NAME_MAX_LENGTH),
    ],
    ids=["over_limit", "multibyte_over_limit", "exact_limit"],
)
async def test_valid_name_truncation_preserves_unicode_codepoints(
    monkeypatch: pytest.MonkeyPatch, name: str, expected_length: int
) -> None:
    """Valid multibyte names are truncated by codepoint, never rewritten."""
    _use_clock(monkeypatch, FakeMonotonic())
    _use_processes(monkeypatch, [_process(1, name_value=name)])

    result = await PsutilProcessReader().read()

    assert isinstance(result, Ok)
    row = result.value.items[0]
    assert len(row.name) == expected_length
    assert not any(0xD800 <= ord(char) <= 0xDFFF for char in row.name)
    assert name.startswith(row.name)
    assert row.name == name[:PROCESS_NAME_MAX_LENGTH]
    row.name.encode("utf-8", errors="strict")


async def test_name_is_not_stripped_or_rewritten(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whitespace and casing from psutil are preserved verbatim."""
    _use_clock(monkeypatch, FakeMonotonic())
    _use_processes(monkeypatch, [_process(1, name_value="  Weird Name  ")])

    result = await PsutilProcessReader().read()

    assert isinstance(result, Ok)
    assert result.value.items[0].name == "  Weird Name  "


async def test_cached_iterator_identity_cannot_hide_pid_reuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale cached create_time cannot attach replacement counters to the old PID."""
    clock = FakeMonotonic()
    _use_clock(monkeypatch, clock)
    cached = _process(500, create_time_value=1.0, cpu_user=10.0)
    _use_processes(monkeypatch, [cached])
    reader = PsutilProcessReader()
    await reader.read()

    replacement = _process(500, create_time_value=2.0, cpu_user=50.0)
    monkeypatch.setattr(psutil, "Process", lambda pid: replacement)
    # Model psutil's stale instance identity but live counter access after reuse.
    cached.cpu_user = 50.0
    clock.now = 101.0
    result = await reader.read()
    assert isinstance(result, Ok)
    assert cached.create_time() == 1.0
    assert result.value.items[0].cpu_percent is None
    assert set(reader._previous) == {(500, 2.0)}

    clock.now = 102.0
    cached.cpu_user = replacement.cpu_user = 52.0
    result = await reader.read()
    assert isinstance(result, Ok)
    assert result.value.items[0].cpu_percent == 200.0
    assert result.partial is False


async def test_identity_change_during_observation_skips_and_drops_baseline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A replacement between counters and the recheck is not a coherent row."""
    clock = FakeMonotonic()
    _use_clock(monkeypatch, clock)
    original = _process(500, cpu_user=10.0)
    _use_processes(monkeypatch, [original])
    reader = PsutilProcessReader()
    await reader.read()

    replacement = _process(500, create_time_value=2.0, cpu_user=50.0)
    observations = iter([original, replacement])
    monkeypatch.setattr(psutil, "Process", lambda pid: next(observations))
    clock.now = 101.0
    result = await reader.read()
    assert isinstance(result, Ok)
    assert result.value.items == ()
    assert result.value.skipped == 1
    assert result.partial is True
    assert reader._previous == {}

    monkeypatch.setattr(psutil, "Process", lambda pid: replacement)
    clock.now = 102.0
    result = await reader.read()
    assert isinstance(result, Ok)
    assert result.value.items[0].cpu_percent is None
    assert result.value.skipped == 0
    assert set(reader._previous) == {(500, 2.0)}


@pytest.mark.parametrize("failure_call", [1, 2], ids=["initial_lookup", "postread_recheck"])
@pytest.mark.parametrize(
    "error",
    [psutil.NoSuchProcess(500), psutil.AccessDenied(500), psutil.ZombieProcess(500), OSError("gone")],
    ids=["gone", "denied", "zombie", "oserror"],
)
async def test_fresh_lookup_failure_safely_skips(
    monkeypatch: pytest.MonkeyPatch, failure_call: int, error: BaseException
) -> None:
    """Both fresh lookup boundaries safely discard inaccessible observations."""
    _use_clock(monkeypatch, FakeMonotonic())
    process = _process(500)
    _use_processes(monkeypatch, [process])
    reader = PsutilProcessReader()
    await reader.read()
    calls = 0

    def lookup(pid: int) -> FakeProcess:
        nonlocal calls
        calls += 1
        if calls == failure_call:
            raise error
        return process

    monkeypatch.setattr(psutil, "Process", lookup)
    result = await reader.read()
    assert isinstance(result, Ok)
    assert result.value.items == ()
    assert result.value.skipped == 1
    assert result.partial is True
    assert reader._previous == {}


@pytest.mark.parametrize("surrogate", ["\ud800", "\udfff", "\udcff"], ids=["high", "low", "surrogateescape"])
@pytest.mark.parametrize("prefix_length", [0, 3, 127, 128, 140], ids=["short", "embedded", "boundary", "after128", "suffix"])
async def test_invalid_full_name_is_skipped_before_truncation(
    monkeypatch: pytest.MonkeyPatch, surrogate: str, prefix_length: int
) -> None:
    """Reject invalid suffixes too; never normalize, replace or truncate them away."""
    clock = FakeMonotonic()
    _use_clock(monkeypatch, clock)
    invalid = _process(1, name_value="a" * prefix_length + surrogate + "tail")
    valid = _process(2, name_value=" e\u0301🛠 ")
    _use_processes(monkeypatch, [invalid, valid])
    reader = PsutilProcessReader()
    await reader.read()
    clock.now = 101.0
    valid.cpu_user = 2.0
    result = await reader.read()
    assert isinstance(result, Ok)
    assert [(row.pid, row.name, row.cpu_percent) for row in result.value.items] == [
        (2, " e\u0301🛠 ", 200.0)
    ]
    assert result.value.skipped == 1
    assert result.partial is True
    assert set(reader._previous) == {(2, 1.0)}


_PRIVATE_PROCESS_DETAILS = (
    "private-process-sentinel",
    "--token=private-command-sentinel",
    "/private/path-sentinel",
    "private-username-sentinel",
)


@pytest.mark.parametrize("error_type", [RuntimeError, PermissionError, psutil.AccessDenied])
async def test_enumeration_diagnostics_exclude_private_exception_details(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    error_type: type[Exception],
) -> None:
    """Even DEBUG formatters must not recover private exception text or traces."""
    _use_clock(monkeypatch, FakeMonotonic())
    details = " ".join(_PRIVATE_PROCESS_DETAILS)
    error = (
        psutil.AccessDenied(pid=123, name=details, msg=details)
        if error_type is psutil.AccessDenied
        else error_type(details)
    )

    def fail() -> list[FakeProcess]:
        raise error

    monkeypatch.setattr(psutil, "process_iter", fail)
    with caplog.at_level(logging.DEBUG, logger=process_module.logger.name):
        result = await PsutilProcessReader().read()

    permission = error_type is not RuntimeError
    assert result == Unavailable(
        UnavailableKind.PERMISSION if permission else UnavailableKind.TRANSIENT,
        "Process information is not readable."
        if permission
        else "Process information is temporarily unavailable.",
    )
    records = [record for record in caplog.records if record.name == process_module.logger.name]
    assert len(records) == 1
    record = records[0]
    expected = "Process enumeration access denied" if permission else "Process enumeration failed"
    assert record.levelno == logging.DEBUG
    assert record.getMessage() == expected
    formatted = logging.Formatter().format(record)
    assert formatted == expected
    for private in (*_PRIVATE_PROCESS_DETAILS, str(error), error_type.__name__, "Traceback"):
        assert private not in record.getMessage()
        assert private not in formatted
    assert record.exc_info is None
    assert record.exc_text is None
    assert record.stack_info is None


async def test_successful_collection_has_no_failure_diagnostics(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Logging changes leave priming and the next CPU delta untouched."""
    clock = FakeMonotonic()
    _use_clock(monkeypatch, clock)
    _use_processes(monkeypatch, [_process(123, cpu_user=1.0)])
    reader = PsutilProcessReader()
    with caplog.at_level(logging.DEBUG, logger=process_module.logger.name):
        first = await reader.read()
        clock.now = 101.0
        _use_processes(monkeypatch, [_process(123, cpu_user=1.5)])
        second = await reader.read()

    assert isinstance(first, Ok)
    assert first.partial is True
    assert first.value.items[0].cpu_percent is None
    assert isinstance(second, Ok)
    assert second.partial is False
    assert [(row.pid, row.cpu_percent) for row in second.value.items] == [(123, 50.0)]
    assert second.value.skipped == 0
    assert not [record for record in caplog.records if record.name == process_module.logger.name]


@pytest.mark.parametrize("error_type", [RuntimeError, PermissionError, psutil.AccessDenied])
async def test_failed_enumeration_recovers_without_changing_cpu_baseline(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    error_type: type[Exception],
) -> None:
    """A failed cycle does not poison the reader or reset its last good baseline."""
    clock = FakeMonotonic()
    _use_clock(monkeypatch, clock)
    _use_processes(monkeypatch, [_process(123, cpu_user=1.0)])
    reader = PsutilProcessReader()
    first = await reader.read()
    assert isinstance(first, Ok)
    assert first.value.items[0].cpu_percent is None

    def fail() -> list[FakeProcess]:
        raise error_type(" ".join(_PRIVATE_PROCESS_DETAILS))

    clock.now = 101.0
    monkeypatch.setattr(psutil, "process_iter", fail)
    with caplog.at_level(logging.DEBUG, logger=process_module.logger.name):
        failed = await reader.read()
        assert isinstance(failed, Unavailable)
        caplog.clear()
        clock.now = 102.0
        _use_processes(monkeypatch, [_process(123, cpu_user=2.0)])
        recovered = await reader.read()

    assert isinstance(recovered, Ok)
    assert recovered.partial is False
    assert recovered.value.skipped == 0
    assert [(row.pid, row.cpu_percent) for row in recovered.value.items] == [(123, 50.0)]
    assert not [record for record in caplog.records if record.name == process_module.logger.name]


async def test_cap_counts_all_readable_processes_before_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``total`` counts readable processes before the cap and is not partial."""
    clock = FakeMonotonic()
    processes = [_process(pid) for pid in (1, 2, 3, 4)]
    _use_clock(monkeypatch, clock)
    _use_processes(monkeypatch, processes)
    reader = PsutilProcessReader(max_processes=2)
    await reader.read()

    clock.now = 101.0
    for index, process in enumerate(processes):
        process.cpu_user = (index + 1) / 100.0
    result = await reader.read()

    assert isinstance(result, Ok)
    assert result.value.total == 4
    assert result.value.total > len(result.value.items)
    assert [row.pid for row in result.value.items] == [4, 3]
    assert result.value.skipped == 0
    assert result.partial is False


async def test_skipped_process_is_excluded_from_total(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zombie and unreadable processes count as skipped, never as total."""
    clock = FakeMonotonic()
    readable = [_process(pid) for pid in (1, 2, 3, 4)]
    unreadable = [
        _process(5, raises=psutil.NoSuchProcess(pid=5)),
        _process(6, status_value=psutil.STATUS_ZOMBIE),
    ]
    _use_clock(monkeypatch, clock)
    _use_processes(monkeypatch, readable + unreadable)
    reader = PsutilProcessReader(max_processes=2)
    await reader.read()

    result = await reader.read()

    assert isinstance(result, Ok)
    assert result.value.total == 4
    assert result.value.skipped == 2
    assert len(result.value.items) == 2
