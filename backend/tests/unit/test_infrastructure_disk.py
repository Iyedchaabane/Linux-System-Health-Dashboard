"""Unit tests for PsutilDiskReader."""

import asyncio
from unittest.mock import patch

import psutil

from monitor.domain.types import Ok, Unavailable
from monitor.infrastructure.psutil_disk import PsutilDiskReader


class TestPsutilDiskReader:
    def test_read_success(self) -> None:
        reader = PsutilDiskReader(path="/")
        result = asyncio.run(reader.read())
        assert isinstance(result, Ok)

    def test_unsupported_when_total_zero(self) -> None:
        with patch("psutil.disk_usage") as mock_du:
            stats = mock_du.return_value
            stats.total = 0
            stats.used = 0
            stats.percent = 0.0
            reader = PsutilDiskReader(path="/")
            result = asyncio.run(reader.read())
            assert isinstance(result, Unavailable)
            assert result.kind == "unsupported"

    def test_permission_error(self) -> None:
        with patch("psutil.disk_usage", side_effect=psutil.AccessDenied(pid=1)):
            reader = PsutilDiskReader(path="/")
            result = asyncio.run(reader.read())
            assert isinstance(result, Unavailable)
            assert result.kind == "permission"

    def test_os_error(self) -> None:
        with patch("psutil.disk_usage", side_effect=OSError("boom")):
            reader = PsutilDiskReader(path="/")
            result = asyncio.run(reader.read())
            assert isinstance(result, Unavailable)
            assert result.kind == "transient"
