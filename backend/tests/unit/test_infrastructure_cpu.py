"""Unit tests for the psutil CPU infrastructure adapter."""

from unittest.mock import MagicMock, patch

from monitor.domain.entities import CpuSnapshot
from monitor.domain.types import Ok, Unavailable, UnavailableKind
from monitor.infrastructure.psutil_cpu import PsutilCpuReader, _get_cpu_executor


class TestPsutilCpuReader:
    """Tests for PsutilCpuReader."""

    def setup_method(self) -> None:
        # Reset executor for each test
        import monitor.infrastructure.psutil_cpu as mod

        mod._cpu_executor = None

    @patch("monitor.infrastructure.psutil_cpu.psutil.cpu_percent")
    @patch("monitor.infrastructure.psutil_cpu.psutil.cpu_count")
    @patch("monitor.infrastructure.psutil_cpu.psutil.cpu_freq")
    @patch("monitor.infrastructure.psutil_cpu.os.getloadavg")
    def test_read_returns_ok_with_all_metrics(
        self, mock_loadavg, mock_freq, mock_count, mock_percent
    ) -> None:
        """Successful read returns Ok with all CPU metrics."""
        mock_percent.return_value = [10.0, 20.0, 30.0, 40.0]
        mock_count.return_value = 4
        mock_freq.return_value = MagicMock(current=2500.0)
        mock_loadavg.return_value = (1.5, 1.2, 1.0)

        reader = PsutilCpuReader()
        result = reader._read_blocking()

        assert isinstance(result, Ok)
        snapshot: CpuSnapshot = result.value
        assert snapshot.cpu_total.value == 25.0  # (10+20+30+40)/4
        assert len(snapshot.per_core) == 4
        assert snapshot.per_core[0].value == 10.0
        assert snapshot.per_core[1].value == 20.0
        assert snapshot.per_core[2].value == 30.0
        assert snapshot.per_core[3].value == 40.0
        assert snapshot.load_average.value == 1.5
        assert snapshot.core_count == 4
        assert snapshot.frequency_hz == 2_500_000_000.0  # 2500 MHz -> Hz

    @patch("monitor.infrastructure.psutil_cpu.psutil.cpu_percent")
    @patch("monitor.infrastructure.psutil_cpu.psutil.cpu_count")
    @patch("monitor.infrastructure.psutil_cpu.psutil.cpu_freq")
    @patch("monitor.infrastructure.psutil_cpu.os.getloadavg")
    def test_read_returns_ok_without_frequency(
        self, mock_loadavg, mock_freq, mock_count, mock_percent
    ) -> None:
        """Successful read without frequency returns Ok with frequency_hz=None."""
        mock_percent.return_value = [10.0, 20.0]
        mock_count.return_value = 2
        mock_freq.return_value = None
        mock_loadavg.return_value = (0.5, 0.3, 0.2)

        reader = PsutilCpuReader()
        result = reader._read_blocking()

        assert isinstance(result, Ok)
        assert result.value.frequency_hz is None

    @patch("monitor.infrastructure.psutil_cpu.psutil.cpu_percent")
    @patch("monitor.infrastructure.psutil_cpu.psutil.cpu_count")
    @patch("monitor.infrastructure.psutil_cpu.os.getloadavg")
    def test_read_frequency_attribute_error_returns_ok(
        self, mock_loadavg, mock_count, mock_percent
    ) -> None:
        """cpu_freq() AttributeError is handled locally, returns Ok with frequency_hz=None."""
        mock_percent.return_value = [10.0]
        mock_count.return_value = 1
        mock_loadavg.return_value = (0.1, 0.1, 0.1)

        import monitor.infrastructure.psutil_cpu as mod

        original_cpu_freq = mod.psutil.cpu_freq
        mod.psutil.cpu_freq = MagicMock(side_effect=AttributeError("no cpu_freq"))
        try:
            reader = PsutilCpuReader()
            result = reader._read_blocking()
        finally:
            mod.psutil.cpu_freq = original_cpu_freq

        assert isinstance(result, Ok)
        assert result.value.frequency_hz is None

    @patch("monitor.infrastructure.psutil_cpu.psutil.cpu_percent")
    @patch("monitor.infrastructure.psutil_cpu.psutil.cpu_count")
    def test_read_no_cores_returns_unavailable(self, mock_count, mock_percent) -> None:
        """Empty per-core list returns Unavailable UNSUPPORTED."""
        mock_percent.return_value = []
        mock_count.return_value = 0

        reader = PsutilCpuReader()
        result = reader._read_blocking()

        assert isinstance(result, Unavailable)
        assert result.kind == UnavailableKind.UNSUPPORTED
        assert result.reason == "No CPU cores detected"

    @patch("monitor.infrastructure.psutil_cpu.psutil.cpu_percent")
    @patch("monitor.infrastructure.psutil_cpu.psutil.cpu_count")
    def test_read_cpu_count_none_returns_unavailable(self, mock_count, mock_percent) -> None:
        """cpu_count() returning None returns Unavailable UNSUPPORTED."""
        mock_percent.return_value = [10.0]
        mock_count.return_value = None

        reader = PsutilCpuReader()
        result = reader._read_blocking()

        assert isinstance(result, Unavailable)
        assert result.kind == UnavailableKind.UNSUPPORTED
        assert result.reason == "CPU core count unavailable"

    @patch("monitor.infrastructure.psutil_cpu.psutil.cpu_percent")
    @patch("monitor.infrastructure.psutil_cpu.psutil.cpu_count")
    def test_read_core_count_mismatch_returns_unavailable(self, mock_count, mock_percent) -> None:
        """Mismatch between per-core count and cpu_count returns Unavailable."""
        mock_percent.return_value = [10.0, 20.0, 30.0]  # 3 cores
        mock_count.return_value = 4  # but count says 4

        reader = PsutilCpuReader()
        result = reader._read_blocking()

        assert isinstance(result, Unavailable)
        assert result.kind == UnavailableKind.UNSUPPORTED
        assert result.reason == "CPU core count mismatch"

    @patch("monitor.infrastructure.psutil_cpu.psutil.cpu_percent")
    @patch("monitor.infrastructure.psutil_cpu.psutil.cpu_count")
    @patch("monitor.infrastructure.psutil_cpu.os.getloadavg")
    def test_read_loadavg_oserror_returns_unavailable(
        self, mock_loadavg, mock_count, mock_percent
    ) -> None:
        """os.getloadavg() OSError returns Unavailable UNSUPPORTED."""
        mock_percent.return_value = [10.0]
        mock_count.return_value = 1
        mock_loadavg.side_effect = OSError("no loadavg")

        reader = PsutilCpuReader()
        result = reader._read_blocking()

        assert isinstance(result, Unavailable)
        assert result.kind == UnavailableKind.UNSUPPORTED
        assert result.reason == "Load average unavailable"

    @patch("monitor.infrastructure.psutil_cpu.psutil.cpu_percent")
    def test_read_access_denied_returns_unavailable_permission(self, mock_percent) -> None:
        """psutil.AccessDenied returns Unavailable PERMISSION."""
        import psutil

        mock_percent.side_effect = psutil.AccessDenied("denied")

        # Need to mock the priming call in __init__ as well
        with patch("monitor.infrastructure.psutil_cpu._get_cpu_executor") as mock_executor:
            mock_exec = MagicMock()
            mock_exec.submit.return_value.result.return_value = None
            mock_executor.return_value = mock_exec

            reader = PsutilCpuReader()
            # Now change side_effect for the actual read call
            mock_percent.side_effect = psutil.AccessDenied("denied")
            result = reader._read_blocking()

        assert isinstance(result, Unavailable)
        assert result.kind == UnavailableKind.PERMISSION
        assert result.reason == "CPU metrics require elevated privileges"

    @patch("monitor.infrastructure.psutil_cpu.psutil.cpu_percent")
    def test_read_permission_error_returns_unavailable_permission(self, mock_percent) -> None:
        """PermissionError returns Unavailable PERMISSION."""
        mock_percent.side_effect = PermissionError("denied")

        with patch("monitor.infrastructure.psutil_cpu._get_cpu_executor") as mock_executor:
            mock_exec = MagicMock()
            mock_exec.submit.return_value.result.return_value = None
            mock_executor.return_value = mock_exec

            reader = PsutilCpuReader()
            mock_percent.side_effect = PermissionError("denied")
            result = reader._read_blocking()

        assert isinstance(result, Unavailable)
        assert result.kind == UnavailableKind.PERMISSION

    @patch("monitor.infrastructure.psutil_cpu.psutil.cpu_percent")
    def test_read_psutil_error_returns_unavailable_transient(self, mock_percent) -> None:
        """psutil.Error returns Unavailable TRANSIENT."""
        import psutil

        mock_percent.side_effect = psutil.Error("transient")

        with patch("monitor.infrastructure.psutil_cpu._get_cpu_executor") as mock_executor:
            mock_exec = MagicMock()
            mock_exec.submit.return_value.result.return_value = None
            mock_executor.return_value = mock_exec

            reader = PsutilCpuReader()
            mock_percent.side_effect = psutil.Error("transient")
            result = reader._read_blocking()

        assert isinstance(result, Unavailable)
        assert result.kind == UnavailableKind.TRANSIENT
        assert result.reason == "CPU read temporarily failed"


class TestCpuExecutor:
    """Tests for the single-thread CPU executor."""

    def setup_method(self) -> None:
        import monitor.infrastructure.psutil_cpu as mod

        mod._cpu_executor = None

    def test_get_cpu_executor_returns_same_instance(self) -> None:
        """_get_cpu_executor returns the same instance on repeated calls."""
        executor1 = _get_cpu_executor()
        executor2 = _get_cpu_executor()
        assert executor1 is executor2
        assert executor1._max_workers == 1
