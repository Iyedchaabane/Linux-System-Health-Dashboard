"""FastAPI dependencies for the Linux System Health Dashboard API."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import Request

from monitor.application.ports import HistoryStore
from monitor.config.settings import Settings
from monitor.domain.entities import SystemSnapshot

SnapshotProvider = Callable[[], Awaitable[SystemSnapshot | None]]


def get_settings(request: Request) -> Settings:
    """Read validated settings from the composition root container."""
    container = request.app.state.container
    return cast(Settings, container.settings)


def get_history_store(request: Request) -> HistoryStore:
    """Read the history store port from the composition root container."""
    container = request.app.state.container
    return cast(HistoryStore, container.history_store)


def get_snapshot_provider(request: Request) -> SnapshotProvider:
    """Read the snapshot provider from the composition root container."""
    container = request.app.state.container
    provider = container.snapshot_provider
    if provider is None:
        raise RuntimeError("Snapshot provider is not configured")
    return cast(Callable[[], Awaitable[SystemSnapshot | None]], provider)
