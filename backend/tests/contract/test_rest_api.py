"""Contract tests for the REST API v1."""

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from monitor.config.settings import Settings
from monitor.domain.entities import CpuSnapshot, MemorySnapshot, SystemSnapshot
from monitor.domain.types import MetricResult, Ok, Unavailable, UnavailableKind
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
from monitor.presentation.api.errors import ApiError

pytestmark = pytest.mark.integration


class FakeSnapshotProvider:
    """Deterministic snapshot provider for contract tests."""

    def __init__(self, snapshot: SystemSnapshot) -> None:

        self._snapshot = snapshot

    async def __call__(self) -> SystemSnapshot:

        return self._snapshot


class FakeHistoryStore:
    """Fake history store for contract tests."""

    def __init__(self, snapshots: list[SystemSnapshot]) -> None:

        self._snapshots = snapshots

    async def append(self, snapshot: SystemSnapshot, occurred_at_utc: UtcTimestamp) -> None:
        """Store an appended snapshot."""

    async def query(self, window_seconds: int, limit: int) -> list[SystemSnapshot]:
        """Return the configured fake snapshots."""

        return self._snapshots


def _now(seconds: float) -> MonotonicTimestamp:

    return MonotonicTimestamp(seconds=seconds)


def _utc_now(seconds: float) -> UtcTimestamp:

    return UtcTimestamp(moment=datetime.fromtimestamp(seconds, tz=UTC))


def _ok_cpu() -> CpuSnapshot:
    """Build a valid CPU snapshot."""

    return CpuSnapshot(
        cpu_total=Percent(value=12.5),
        per_core=(Percent(value=12.5),),
        load_average=LoadAverage(value=0.0),
        core_count=1,
    )


def _ok_memory() -> MemorySnapshot:
    """Build a valid memory snapshot."""

    return MemorySnapshot(
        total=Bytes(value=1024),
        available=Bytes(value=512),
        used_percent=Percent(value=50.0),
        swap=SwapUsage(total=Bytes(value=0), used=Bytes(value=0)),
    )


def _unavailable_cpu() -> MetricResult[CpuSnapshot]:

    from monitor.domain.types import Unavailable, UnavailableKind

    return Unavailable(kind=UnavailableKind.UNSUPPORTED, reason="cpu snapshot unavailable")


def _unavailable_memory() -> MetricResult[MemorySnapshot]:

    from monitor.domain.types import Unavailable, UnavailableKind

    return Unavailable(kind=UnavailableKind.UNSUPPORTED, reason="memory snapshot unavailable")


def _error_body(response: Any) -> dict[str, Any]:
    """Return the canonical error body."""

    body: dict[str, Any] = response.json()

    assert "error" in body

    error = body["error"]

    assert isinstance(error, dict)

    assert isinstance(error.get("code"), str)

    assert isinstance(error.get("message"), str)

    assert isinstance(error.get("request_id"), str)

    return body


@pytest.mark.integration
async def test_healthz_returns_ok_status() -> None:
    """The health endpoint returns the approved OK response."""

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/healthz")

    assert response.status_code == 200

    assert response.json() == {"status": "ok"}


@pytest.mark.integration
async def test_readyz_returns_ok_when_snapshot_is_fresh() -> None:
    """The readiness endpoint returns OK for a fresh snapshot."""

    app = create_app()

    provider = FakeSnapshotProvider(
        SystemSnapshot(
            cpu=Ok(_ok_cpu()),
            memory=Ok(_ok_memory()),
            disk=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming"),
            network=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming"),
            timestamp_monotonic=_now(1.0),
            timestamp_utc=_utc_now(1.0),
        )
    )

    import time as _time

    provider = FakeSnapshotProvider(
        SystemSnapshot(
            cpu=Ok(_ok_cpu()),
            memory=Ok(_ok_memory()),
            disk=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming"),
            network=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming"),
            timestamp_monotonic=MonotonicTimestamp(seconds=_time.monotonic()),
            timestamp_utc=_utc_now(1.0),
        )
    )

    app.dependency_overrides[get_settings] = lambda: Settings()

    app.dependency_overrides[get_snapshot_provider] = lambda: provider

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/readyz")

    assert response.status_code == 200

    assert response.json() == {"status": "ok"}


@pytest.mark.integration
async def test_readyz_returns_not_ready_error_when_snapshot_is_stale() -> None:
    """The readiness endpoint returns the approved NOT_READY error when stale."""

    app = create_app()

    provider = FakeSnapshotProvider(
        SystemSnapshot(
            cpu=Ok(_ok_cpu()),
            memory=Ok(_ok_memory()),
            disk=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming"),
            network=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming"),
            timestamp_monotonic=MonotonicTimestamp(seconds=__import__("time").monotonic() - 100.0),
            timestamp_utc=_utc_now(10.0),
        )
    )

    app.dependency_overrides[get_settings] = lambda: Settings()

    app.dependency_overrides[get_snapshot_provider] = lambda: provider

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/readyz")

    assert response.status_code == 503

    body = _error_body(response)

    assert body["error"]["code"] == "NOT_READY"


@pytest.mark.integration
async def test_snapshot_returns_ok_group_states() -> None:
    """The snapshot endpoint returns the approved REST snapshot schema."""

    app = create_app()

    provider = FakeSnapshotProvider(
        SystemSnapshot(
            cpu=Ok(_ok_cpu()),
            memory=Ok(_ok_memory()),
            disk=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming"),
            network=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming"),
            timestamp_monotonic=_now(0.0),
            timestamp_utc=_utc_now(0.0),
        )
    )

    app.dependency_overrides[get_snapshot_provider] = lambda: provider

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/snapshot")

    assert response.status_code == 200

    assert response.json() == {
        "ts": 0,
        "groups": {
            "cpu": {
                "status": "ok",
                "value": {
                    "cpu_total": 12.5,
                    "per_core": [12.5],
                    "load_average": 0.0,
                    "core_count": 1,
                    "frequency_hz": None,
                },
                "partial": False,
            },
            "memory": {
                "status": "ok",
                "value": {"total": 1024, "available": 512, "used_percent": 50.0},
                "partial": False,
            },
            "disk": {"status": "unavailable", "kind": "transient", "reason": "warming"},
            "network": {"status": "unavailable", "kind": "transient", "reason": "warming"},
        },
        "meta": None,
    }


@pytest.mark.integration
async def test_snapshot_reports_unavailable_group_when_snapshot_is_missing() -> None:
    """The snapshot endpoint reports unavailable groups honestly."""

    app = create_app()

    provider = FakeSnapshotProvider(
        SystemSnapshot(
            cpu=_unavailable_cpu(),
            memory=Ok(_ok_memory()),
            disk=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming"),
            network=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming"),
            timestamp_monotonic=_now(0.0),
            timestamp_utc=_utc_now(0.0),
        )
    )

    app.dependency_overrides[get_snapshot_provider] = lambda: provider

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/snapshot")

    assert response.status_code == 200

    body = response.json()

    assert body["groups"]["cpu"]["status"] == "unavailable"

    assert body["groups"]["cpu"]["kind"] == "unsupported"

    assert body["groups"]["memory"]["status"] == "ok"


@pytest.mark.integration
async def test_history_returns_scalar_series() -> None:
    """The history endpoint returns the approved scalar series response."""

    app = create_app()

    history_store = FakeHistoryStore(
        [
            SystemSnapshot(
                cpu=Ok(_ok_cpu()),
                memory=_unavailable_memory(),
                disk=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming"),
                network=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming"),
                timestamp_monotonic=_now(0.0),
                timestamp_utc=_utc_now(0.0),
            ),
            SystemSnapshot(
                cpu=Ok(_ok_cpu()),
                memory=_unavailable_memory(),
                disk=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming"),
                network=Unavailable(kind=UnavailableKind.TRANSIENT, reason="warming"),
                timestamp_monotonic=_now(1.0),
                timestamp_utc=_utc_now(1.0),
            ),
        ]
    )

    app.dependency_overrides[get_settings] = lambda: Settings()

    app.dependency_overrides[get_history_store] = lambda: history_store

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/history",
            params={"group": "cpu", "from": 0, "to": 1000},
        )

    assert response.status_code == 200

    assert response.json() == {
        "group": "cpu",
        "points": [
            {"ts": 0, "value": 12.5},
            {"ts": 1000, "value": 12.5},
        ],
    }


@pytest.mark.integration
async def test_history_unknown_group_returns_invalid_query() -> None:
    """The history endpoint rejects an unknown metric group."""

    app = create_app()

    history_store = FakeHistoryStore([])

    app.dependency_overrides[get_settings] = lambda: Settings()

    app.dependency_overrides[get_history_store] = lambda: history_store

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/history",
            params={"group": "unknown", "from": 0, "to": 1000},
        )

    assert response.status_code == 400

    body = _error_body(response)

    assert body["error"]["code"] == "INVALID_QUERY"


@pytest.mark.integration
async def test_history_invalid_range_returns_invalid_query() -> None:
    """The history endpoint rejects a reversed or empty time range."""

    app = create_app()

    history_store = FakeHistoryStore([])

    app.dependency_overrides[get_settings] = lambda: Settings()

    app.dependency_overrides[get_history_store] = lambda: history_store

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/history",
            params={"group": "cpu", "from": 1000, "to": 1000},
        )

    assert response.status_code == 400

    body = _error_body(response)

    assert body["error"]["code"] == "INVALID_QUERY"


@pytest.mark.integration
async def test_history_window_exceeds_retention_returns_invalid_query() -> None:
    """The history endpoint rejects windows beyond the retention limit."""

    app = create_app()

    history_store = FakeHistoryStore([])

    app.dependency_overrides[get_settings] = lambda: Settings()

    app.dependency_overrides[get_history_store] = lambda: history_store

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/history",
            params={"group": "cpu", "from": 0, "to": 3_600_001},
        )

    assert response.status_code == 400

    body = _error_body(response)

    assert body["error"]["code"] == "INVALID_QUERY"


@pytest.mark.integration
async def test_history_validation_error_returns_invalid_request() -> None:
    """The history endpoint maps request validation failures to INVALID_REQUEST."""

    app = create_app()

    history_store = FakeHistoryStore([])

    app.dependency_overrides[get_settings] = lambda: Settings()

    app.dependency_overrides[get_history_store] = lambda: history_store

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/history")

    assert response.status_code == 422

    body = _error_body(response)

    assert body["error"]["code"] == "INVALID_REQUEST"


@pytest.mark.integration
async def test_snapshot_internal_error_returns_internal_error() -> None:
    """The snapshot endpoint maps unexpected failures to INTERNAL_ERROR."""

    async def failing_snapshot_provider() -> SystemSnapshot:

        raise RuntimeError("boom")

    app = create_app()

    app.dependency_overrides[get_snapshot_provider] = failing_snapshot_provider

    transport = ASGITransport(app=app, raise_app_exceptions=False)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/snapshot")

    assert response.status_code == 500

    body = _error_body(response)

    assert body["error"]["code"] == "INTERNAL_ERROR"


@pytest.mark.integration
async def test_rate_limit_error_returns_rate_limited_status() -> None:
    """The error handler maps RATE_LIMITED to its approved HTTP status."""

    async def rate_limited_snapshot_provider() -> SystemSnapshot:

        raise ApiError(
            code="RATE_LIMITED",
            message="Too many requests",
            status_code=429,
        )

    app = create_app()

    app.dependency_overrides[get_snapshot_provider] = rate_limited_snapshot_provider

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/snapshot")

    assert response.status_code == 429

    body = _error_body(response)

    assert body["error"]["code"] == "RATE_LIMITED"
