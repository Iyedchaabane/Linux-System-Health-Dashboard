"""Integration test for the real psutil process collector against the host.

Only shape and range invariants are asserted: never exact host values, process
names or counts.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from monitor.domain.entities import PROCESS_NAME_MAX_LENGTH, ProcessInfo
from monitor.domain.types import Ok
from monitor.infrastructure.psutil_process import PsutilProcessReader

pytestmark = pytest.mark.integration


@pytest.fixture
def reader() -> Iterator[PsutilProcessReader]:
    instance = PsutilProcessReader(max_processes=25)
    try:
        yield instance
    finally:
        instance.close()


def _order_key(row: ProcessInfo) -> tuple[int, float, int]:
    """CPU descending with null last, PID ascending for ties."""
    if row.cpu_percent is None:
        return (1, 0.0, row.pid)
    return (0, -row.cpu_percent, row.pid)


async def test_real_reader_returns_bounded_consistent_rows(reader: PsutilProcessReader) -> None:
    """Two consecutive host reads keep every documented row invariant."""
    first = await reader.read()
    second = await reader.read()

    assert isinstance(first, Ok)
    assert isinstance(second, Ok)
    assert len(first.value.items) <= 25
    assert len(second.value.items) <= 25

    # Without a previous sample nothing may look like a real 0 %.
    assert all(row.cpu_percent is None for row in first.value.items)
    # A second read must produce at least one real delta on a live host.
    assert any(row.cpu_percent is not None for row in second.value.items)

    for result in (first, second):
        rows = result.value.items
        pids = [row.pid for row in rows]
        assert len(set(pids)) == len(pids)
        assert all(pid > 0 for pid in pids)
        assert all(1 <= len(row.name) <= PROCESS_NAME_MAX_LENGTH for row in rows)
        assert all(row.memory_rss_bytes >= 0 for row in rows)
        assert all(row.cpu_percent is None or row.cpu_percent >= 0.0 for row in rows)
        assert list(rows) == sorted(rows, key=_order_key)
