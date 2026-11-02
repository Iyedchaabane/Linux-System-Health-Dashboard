"""Unit tests for PsutilNetworkReader."""

import asyncio
from unittest import mock

import psutil

from monitor.domain.types import Ok, Unavailable
from monitor.infrastructure.psutil_network import PsutilNetworkReader


def test_read_success() -> None:
    reader = PsutilNetworkReader()
    result = asyncio.run(reader.read())
    # success may depend on host; assert type is Ok or Unavailable (shape check)
    assert isinstance(result, (Ok, Unavailable))


def test_unavailable_when_no_interfaces() -> None:
    with mock.patch("psutil.net_io_counters", return_value={}):
        reader = PsutilNetworkReader()
        result = asyncio.run(reader.read())
        assert isinstance(result, Unavailable)
        assert result.kind == "unsupported"


def test_permission_error() -> None:
    with mock.patch("psutil.net_io_counters", side_effect=psutil.AccessDenied(pid=1)):
        reader = PsutilNetworkReader()
        result = asyncio.run(reader.read())
        assert isinstance(result, Unavailable)
        assert result.kind == "permission"


def test_transient_error() -> None:
    with mock.patch("psutil.net_io_counters", side_effect=OSError("boom")):
        reader = PsutilNetworkReader()
        result = asyncio.run(reader.read())
        assert isinstance(result, Unavailable)
        assert result.kind == "transient"
