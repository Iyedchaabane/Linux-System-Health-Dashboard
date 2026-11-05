"""Validation tests for the process domain entities."""

from __future__ import annotations

import math
from typing import Any

import pytest

from monitor.domain.entities import PROCESS_NAME_MAX_LENGTH, ProcessInfo, ProcessList


def _valid_process(**overrides: Any) -> ProcessInfo:
    values: dict[str, Any] = {
        "pid": 1,
        "name": "init",
        "cpu_percent": None,
        "memory_rss_bytes": 1024,
    }
    values.update(overrides)
    return ProcessInfo(**values)


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"pid": 0}, ValueError),
        ({"pid": True}, TypeError),
        ({"pid": "1"}, TypeError),
        ({"name": ""}, ValueError),
        ({"name": "a" * (PROCESS_NAME_MAX_LENGTH + 1)}, ValueError),
        ({"cpu_percent": math.inf}, ValueError),
        ({"cpu_percent": -0.1}, ValueError),
        ({"memory_rss_bytes": -1}, ValueError),
        ({"memory_rss_bytes": True}, TypeError),
    ],
    ids=[
        "pid_zero",
        "pid_bool",
        "pid_string",
        "name_empty",
        "name_too_long",
        "cpu_infinite",
        "cpu_negative",
        "rss_negative",
        "rss_bool",
    ],
)
def test_process_info_rejects_invalid_values(overrides: dict[str, Any], error: type[Exception]) -> None:
    """Every invalid row shape is rejected at construction."""
    with pytest.raises(error):
        _valid_process(**overrides)


def test_process_info_preserves_a_missing_cpu_delta() -> None:
    """A missing CPU delta stays None, never a placeholder zero."""
    row = _valid_process(cpu_percent=None)

    assert row.cpu_percent is None
    assert row.name == "init"
    assert row.memory_rss_bytes == 1024


def test_process_info_accepts_cpu_above_one_logical_cpu() -> None:
    """More than 100 % is valid: it means more than one occupied logical CPU."""
    assert _valid_process(cpu_percent=250.0).cpu_percent == 250.0


def test_process_info_accepts_a_name_at_the_limit() -> None:
    """Exactly 128 characters is still valid."""
    name = "a" * PROCESS_NAME_MAX_LENGTH

    assert _valid_process(name=name).name == name


def test_process_list_rejects_negative_skipped() -> None:
    """A skipped count can never be negative."""
    with pytest.raises(ValueError):
        ProcessList(items=(), skipped=-1)


def test_process_list_rejects_bool_skipped() -> None:
    """A boolean is not a skipped count."""
    with pytest.raises(TypeError):
        ProcessList(items=(), skipped=True)


def test_process_list_accepts_an_empty_result() -> None:
    """An empty namespace is a valid complete result."""
    result = ProcessList(items=(), skipped=0)

    assert result.items == ()
    assert result.skipped == 0
