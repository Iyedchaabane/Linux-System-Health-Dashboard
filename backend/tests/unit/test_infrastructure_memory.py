"""Unit tests for the psutil memory infrastructure adapter."""

from unittest.mock import MagicMock, patch

from monitor.domain.entities import MemorySnapshot
from monitor.domain.types import Ok, Unavailable, UnavailableKind
from monitor.infrastructure.psutil_memory import PsutilMemoryReader


class TestPsutilMemoryReader:
    """Tests for PsutilMemoryReader."""

    @patch("monitor.infrastructure.psutil_memory.psutil.virtual_memory")
    @patch("monitor.infrastructure.psutil_memory.psutil.swap_memory")
    def test_read_returns_ok_with_all_metrics(self, mock_swap, mock_vm) -> None:
        """Successful read returns Ok with all memory metrics."""
        mock_vm.return_value = MagicMock(total=8_000_000_000, available=2_000_000_000)
        mock_swap.return_value = MagicMock(total=2_000_000_000, used=500_000_000)

        reader = PsutilMemoryReader()
        result = reader._read_blocking()

        assert isinstance(result, Ok)
        snapshot: MemorySnapshot = result.value
        assert snapshot.total.value == 8_000_000_000
        assert snapshot.available.value == 2_000_000_000
        assert snapshot.used_percent.value == 75.0  # (8-2)/8 * 100
        assert snapshot.swap.total.value == 2_000_000_000
        assert snapshot.swap.used.value == 500_000_000

    @patch("monitor.infrastructure.psutil_memory.psutil.virtual_memory")
    @patch("monitor.infrastructure.psutil_memory.psutil.swap_memory")
    def test_read_returns_ok_with_zero_swap(self, mock_swap, mock_vm) -> None:
        """Successful read with zero swap total returns Ok with swap usage zero."""
        mock_vm.return_value = MagicMock(total=4_000_000_000, available=3_000_000_000)
        mock_swap.return_value = MagicMock(total=0, used=0)

        reader = PsutilMemoryReader()
        result = reader._read_blocking()

        assert isinstance(result, Ok)
        snapshot: MemorySnapshot = result.value
        assert snapshot.swap.total.value == 0
        assert snapshot.swap.used.value == 0
        assert snapshot.swap.percent == 0.0

    @patch("monitor.infrastructure.psutil_memory.psutil.virtual_memory")
    def test_read_zero_total_returns_unavailable(self, mock_vm) -> None:
        """virtual_memory().total <= 0 returns Unavailable UNSUPPORTED."""
        mock_vm.return_value = MagicMock(total=0, available=0)

        reader = PsutilMemoryReader()
        result = reader._read_blocking()

        assert isinstance(result, Unavailable)
        assert result.kind == UnavailableKind.UNSUPPORTED
        assert result.reason == "Memory total unavailable"

    @patch("monitor.infrastructure.psutil_memory.psutil.virtual_memory")
    def test_read_access_denied_returns_unavailable_permission(self, mock_vm) -> None:
        """psutil.AccessDenied returns Unavailable PERMISSION."""
        import psutil

        mock_vm.side_effect = psutil.AccessDenied("denied")

        reader = PsutilMemoryReader()
        result = reader._read_blocking()

        assert isinstance(result, Unavailable)
        assert result.kind == UnavailableKind.PERMISSION
        assert result.reason == "Memory metrics require elevated privileges"

    @patch("monitor.infrastructure.psutil_memory.psutil.virtual_memory")
    def test_read_permission_error_returns_unavailable_permission(self, mock_vm) -> None:
        """PermissionError returns Unavailable PERMISSION."""
        mock_vm.side_effect = PermissionError("denied")

        reader = PsutilMemoryReader()
        result = reader._read_blocking()

        assert isinstance(result, Unavailable)
        assert result.kind == UnavailableKind.PERMISSION

    @patch("monitor.infrastructure.psutil_memory.psutil.virtual_memory")
    def test_read_psutil_error_returns_unavailable_transient(self, mock_vm) -> None:
        """psutil.Error returns Unavailable TRANSIENT."""
        import psutil

        mock_vm.side_effect = psutil.Error("transient")

        reader = PsutilMemoryReader()
        result = reader._read_blocking()

        assert isinstance(result, Unavailable)
        assert result.kind == UnavailableKind.TRANSIENT
        assert result.reason == "Memory read temporarily failed"
