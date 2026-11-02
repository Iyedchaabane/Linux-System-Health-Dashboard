"""Health and readiness REST routes."""

from __future__ import annotations

import time
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request

from monitor.config.settings import Settings
from monitor.domain.ports import Clock
from monitor.presentation.api.deps import SnapshotProvider, get_settings, get_snapshot_provider
from monitor.presentation.api.errors import ApiError
from monitor.presentation.api.schemas import HealthResponse

router = APIRouter(prefix="/api/v1")


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    """Return process health."""
    return HealthResponse(status="ok")


@router.get("/readyz", response_model=HealthResponse)
async def readyz(
    request: Request,
    snapshot_provider: Annotated[SnapshotProvider, Depends(get_snapshot_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    """Return readiness based on the age of the freshest snapshot.

    A snapshot is considered fresh for up to twice the configured sample
    interval, matching the staleness rule documented in AGENTS.md.
    """
    snapshot = await snapshot_provider()
    if snapshot is None:
        raise ApiError(code="NOT_READY", message="No snapshot yet", status_code=503)

    container = getattr(request.app.state, "container", None)
    if container is not None and getattr(container, "clock", None) is not None:
        now_seconds = cast(Clock, container.clock).monotonic().seconds
    else:
        now_seconds = time.monotonic()
    age_seconds = now_seconds - snapshot.timestamp_monotonic.seconds

    threshold_seconds = settings.sample_interval_seconds * 2.0
    if age_seconds > threshold_seconds:
        raise ApiError(
            code="NOT_READY",
            message="No fresh snapshot available",
            status_code=503,
        )
    return HealthResponse(status="ok")
