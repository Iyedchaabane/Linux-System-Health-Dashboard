"""Shared pytest fixtures for the Linux System Health Dashboard backend."""

import pytest

from monitor.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Provide a Settings instance with validated defaults."""
    return Settings()
