"""Unit tests for application settings: defaults, overrides and validation."""

import pytest
from pydantic import ValidationError

from monitor.config import Settings, load_settings


def test_defaults() -> None:
    """Settings expose the approved defaults."""
    s = Settings()
    assert s.host == "127.0.0.1"
    assert s.port == 8080
    assert s.workers == 1
    assert s.sample_interval_seconds == 1.0
    assert s.max_ws_clients == 100
    assert s.max_ws_clients_per_ip == 10
    assert s.ws_queue_size == 4
    assert s.ws_send_timeout_seconds == 5.0
    assert s.ws_handshake_timeout_seconds == 5.0
    assert s.ws_max_message_size == 4096
    assert s.ws_rate_limit_burst == 10
    assert s.ws_rate_limit_refill == 2.0
    assert s.history_max_seconds == 3600
    assert s.max_processes_in_stream == 25
    assert s.max_processes_in_rest == 100
    assert s.process_procfs_path == "/proc"
    assert s.snapshot_size_budget_bytes == 16384
    assert s.allowed_origins == []
    assert s.docs_enabled is True
    assert s.log_level == "INFO"
    assert s.log_json is False
    assert s.collection_timeout_multiplier == 3.0


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables override the approved defaults."""
    monkeypatch.setenv("MONITOR_HOST", "0.0.0.0")
    monkeypatch.setenv("MONITOR_PORT", "9000")
    monkeypatch.setenv("MONITOR_SAMPLE_INTERVAL_SECONDS", "2.0")
    monkeypatch.setenv("MONITOR_MAX_WS_CLIENTS", "42")
    monkeypatch.setenv("MONITOR_WS_QUEUE_SIZE", "6")
    monkeypatch.setenv("MONITOR_PROCESS_PROCFS_PATH", "/host/proc")
    s = Settings()
    assert s.host == "0.0.0.0"
    assert s.port == 9000
    assert s.sample_interval_seconds == 2.0
    assert s.max_ws_clients == 42
    assert s.ws_queue_size == 6
    assert s.process_procfs_path == "/host/proc"


def test_empty_process_procfs_path_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """The procfs root must be a non-empty path."""
    monkeypatch.setenv("MONITOR_PROCESS_PROCFS_PATH", "")
    with pytest.raises(ValidationError):
        Settings()


def test_invalid_port_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """An out-of-range port must fail fast with a validation error."""
    monkeypatch.setenv("MONITOR_PORT", "99999")
    with pytest.raises(ValidationError):
        Settings()


def test_invalid_sample_interval_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A sampling interval below the approved floor must fail validation."""
    monkeypatch.setenv("MONITOR_SAMPLE_INTERVAL_SECONDS", "0.5")
    with pytest.raises(ValidationError):
        Settings()


def test_load_settings_returns_valid_instance() -> None:
    """load_settings returns a Settings instance that is valid."""
    assert isinstance(load_settings(), Settings)


def test_production_requires_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONITOR_ENVIRONMENT", "production")
    monkeypatch.delenv("MONITOR_ALLOWED_ORIGINS", raising=False)
    with pytest.raises(ValidationError):
        Settings(allowed_origins=[])


def test_production_rejects_wildcard_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONITOR_ENVIRONMENT", "production")
    with pytest.raises(ValidationError):
        Settings(allowed_origins=["http://example.com", "*"])


def test_development_allows_empty_origins() -> None:
    s = Settings(environment="development", allowed_origins=[])
    assert s.allowed_origins == []


def test_testing_environment_allows_empty_origins() -> None:
    s = Settings(environment="testing", allowed_origins=[])
    assert s.allowed_origins == []
