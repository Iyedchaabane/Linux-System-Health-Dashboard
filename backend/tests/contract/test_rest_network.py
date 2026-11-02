"""REST tests for network metrics."""

from __future__ import annotations

from datetime import UTC

import pytest
from httpx import ASGITransport, AsyncClient

from monitor.config import Settings
from monitor.domain.entities import (
    CpuSnapshot,
    DiskUsage,
    MemorySnapshot,
    NetCounters,
    SystemSnapshot,
)
from monitor.domain.types import Ok, Unavailable, UnavailableKind
from monitor.domain.values import (
    Bytes,
    LoadAverage,
    MonotonicTimestamp,
    Percent,
    SwapUsage,
    UtcTimestamp,
)
from monitor.presentation.api.app import create_app
from monitor.presentation.api.deps import get_history_store, get_settings, get_snapshot_provider


def _now(seconds: float) -> MonotonicTimestamp:
    return MonotonicTimestamp(seconds=seconds)


def _utc_now(seconds: float) -> UtcTimestamp:
    from datetime import datetime

    return UtcTimestamp(moment=datetime.fromtimestamp(seconds, tz=UTC))


def _ok_cpu() -> CpuSnapshot:
    return CpuSnapshot(
        cpu_total=Percent(value=12.5),
        per_core=(Percent(value=12.5),),
        load_average=LoadAverage(value=0.0),
        core_count=1,
    )


def _ok_memory() -> MemorySnapshot:
    return MemorySnapshot(
        total=Bytes(value=1024),
        available=Bytes(value=512),
        used_percent=Percent(value=50.0),
        swap=SwapUsage(total=Bytes(value=0), used=Bytes(value=0)),
    )


@pytest.mark.integration
async def test_rest_network_available() -> None:
    app = create_app()

    async def provider() -> SystemSnapshot:
        return SystemSnapshot(
            cpu=Ok(_ok_cpu()),
            memory=Ok(_ok_memory()),
            disk=Ok(
                DiskUsage(
                    device="/",
                    total=Bytes(value=1),
                    used=Bytes(value=1),
                    percent=Percent(value=1.0),
                )
            ),
            network=Ok(
                NetCounters(
                    rx_bytes=Bytes(value=100),
                    tx_bytes=Bytes(value=50),
                    sampled_at=MonotonicTimestamp(seconds=1.0),
                )
            ),
            timestamp_monotonic=_now(0.0),
            timestamp_utc=_utc_now(0.0),
        )

    app.dependency_overrides[get_snapshot_provider] = lambda: provider
    app.dependency_overrides[get_settings] = lambda: Settings()
    app.dependency_overrides[get_history_store] = lambda: None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/snapshot")

    assert response.status_code == 200
    body = response.json()
    assert body["groups"]["network"] == {
        "status": "ok",
        "value": {"rx_bytes": 100, "tx_bytes": 50},
        "partial": False,
    }


@pytest.mark.integration
async def test_rest_network_unavailable() -> None:
    app = create_app()

    async def provider() -> SystemSnapshot:
        return SystemSnapshot(
            cpu=Ok(_ok_cpu()),
            memory=Ok(_ok_memory()),
            disk=Ok(
                DiskUsage(
                    device="/",
                    total=Bytes(value=1),
                    used=Bytes(value=1),
                    percent=Percent(value=1.0),
                )
            ),
            network=Unavailable(kind=UnavailableKind.PERMISSION, reason="denied"),
            timestamp_monotonic=_now(0.0),
            timestamp_utc=_utc_now(0.0),
        )

    app.dependency_overrides[get_snapshot_provider] = lambda: provider
    app.dependency_overrides[get_settings] = lambda: Settings()
    app.dependency_overrides[get_history_store] = lambda: None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/snapshot")

    assert response.status_code == 200
    body = response.json()
    assert body["groups"]["network"] == {
        "status": "unavailable",
        "kind": "permission",
        "reason": "denied",
    }
