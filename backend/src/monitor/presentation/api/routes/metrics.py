"""REST metrics routes for the Linux System Health Dashboard."""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, Request

from monitor.application.ports import HistoryStore
from monitor.config.settings import Settings
from monitor.domain.entities import (
    CpuSnapshot,
    DiskUsage,
    MemorySnapshot,
    NetCounters,
    ProcessList,
)
from monitor.domain.types import MetricResult, Ok
from monitor.presentation.api.deps import (
    SnapshotProvider,
    get_history_store,
    get_settings,
    get_snapshot_provider,
)
from monitor.presentation.api.errors import ApiError
from monitor.presentation.api.schemas import HistoryPoint, HistoryResponse, SnapshotResponse
from monitor.presentation.ws.budget import (
    DEFAULT_SNAPSHOT_BUDGET_BYTES,
    SnapshotBudgetExceeded,
    compact_json,
    enforce_snapshot_budget,
    fit_snapshot_to_budget,
)
from monitor.presentation.ws.protocol import (
    GroupStateOk,
    GroupStateUnavailable,
    ProcessesStateOk,
    ProcessesValue,
    ProcessRow,
)

router = APIRouter(prefix="/api/v1")

ALLOWED_GROUPS = frozenset({"cpu", "memory", "disk", "network", "process", "sensor"})


def _map_cpu_result(
    result: MetricResult[CpuSnapshot],
) -> GroupStateOk | GroupStateUnavailable:
    """Map a CPU MetricResult onto the WebSocket v1 group-state contract."""
    if isinstance(result, Ok):
        v = result.value
        return GroupStateOk(
            status="ok",
            value={
                "cpu_total": v.cpu_total.value,
                "per_core": [p.value if p is not None else None for p in v.per_core],
                "load_average": v.load_average.value,
                "core_count": v.core_count,
                "frequency_hz": v.frequency_hz,
            },
            partial=result.partial,
        )
    return GroupStateUnavailable(
        status="unavailable",
        kind=result.kind,
        reason=result.reason,
    )


def _map_memory_result(
    result: MetricResult[MemorySnapshot],
) -> GroupStateOk | GroupStateUnavailable:
    """Map a memory MetricResult onto the WebSocket v1 group-state contract."""
    if isinstance(result, Ok):
        v = result.value
        return GroupStateOk(
            status="ok",
            value={
                "total": v.total.value,
                "available": v.available.value,
                "used_percent": v.used_percent.value,
            },
            partial=result.partial,
        )
    return GroupStateUnavailable(
        status="unavailable",
        kind=result.kind,
        reason=result.reason,
    )


def _map_disk_result(
    result: MetricResult[DiskUsage],
) -> GroupStateOk | GroupStateUnavailable:
    """Map a disk MetricResult onto the WebSocket v1 group-state contract."""
    if isinstance(result, Ok):
        v = result.value
        return GroupStateOk(
            status="ok",
            value={
                "device": v.device,
                "total": v.total.value,
                "used": v.used.value,
                "percent": v.percent.value,
            },
            partial=result.partial,
        )
    return GroupStateUnavailable(
        status="unavailable",
        kind=result.kind,
        reason=result.reason,
    )


def _map_network_result(
    result: MetricResult[NetCounters],
) -> GroupStateOk | GroupStateUnavailable:
    """Map a network MetricResult onto the WebSocket v1 group-state contract."""
    if isinstance(result, Ok):
        v = result.value
        return GroupStateOk(
            status="ok",
            value={
                "rx_bytes": v.rx_bytes.value,
                "tx_bytes": v.tx_bytes.value,
            },
            partial=result.partial,
        )
    return GroupStateUnavailable(
        status="unavailable",
        kind=result.kind,
        reason=result.reason,
    )


def _map_processes_result(
    result: MetricResult[ProcessList],
) -> ProcessesStateOk | GroupStateUnavailable:
    """Map a ProcessList MetricResult onto the WebSocket v1 processes group.

    Rows keep the collector's order, cap and values: nothing is re-sorted,
    re-truncated, renamed or clamped, and ``cpu_percent=None`` stays ``None``.
    """
    if isinstance(result, Ok):
        v = result.value
        return ProcessesStateOk(
            status="ok",
            partial=result.partial,
            value=ProcessesValue(
                items=[
                    ProcessRow(
                        pid=item.pid,
                        name=item.name,
                        cpu_percent=item.cpu_percent,
                        memory_rss_bytes=item.memory_rss_bytes,
                    )
                    for item in v.items
                ],
                skipped=v.skipped,
            ),
        )
    return GroupStateUnavailable(
        status="unavailable",
        kind=result.kind,
        reason=result.reason,
    )


@router.get("/snapshot", response_model=SnapshotResponse)
async def snapshot(
    request: Request,
    snapshot_provider: Annotated[SnapshotProvider, Depends(get_snapshot_provider)],
) -> SnapshotResponse:
    """Return the latest cached snapshot."""
    snap = await snapshot_provider()
    if snap is None:
        raise ApiError(
            code="snapshot_not_ready", message="No snapshot collected yet", status_code=503
        )
    ts = int(snap.timestamp_utc.moment.timestamp() * 1000)
    groups: dict[str, Any] = {
        "cpu": _map_cpu_result(snap.cpu).model_dump(mode="json"),
        "memory": _map_memory_result(snap.memory).model_dump(mode="json"),
        "disk": _map_disk_result(snap.disk).model_dump(mode="json"),
        "network": _map_network_result(snap.network).model_dump(mode="json"),
    }
    if snap.processes is not None:
        groups["processes"] = _map_processes_result(snap.processes).model_dump(mode="json")

    # Use the shared degradation policy with transport-specific sizing. The
    # container is absent only in tests that exercise the route without the
    # application lifespan.
    container = getattr(request.app.state, "container", None)
    budget_bytes = (
        cast(int, container.settings.snapshot_size_budget_bytes)
        if container is not None
        else DEFAULT_SNAPSHOT_BUDGET_BYTES
    )
    # Select groups using the canonical WebSocket shape (seq=1, drops=0), not
    # the REST body. Actual stream seq/drop metadata can change availability
    # near budget boundaries, even for the same source snapshot timestamp.
    try:
        fit_snapshot_to_budget(
            groups,
            lambda candidate: compact_json(
                {
                    "v": 1,
                    "type": "snapshot",
                    "seq": 1,
                    "ts": ts,
                    "data": {
                        "type": "snapshot",
                        "groups": candidate,
                        "meta": {"dropped_since_last": 0},
                    },
                }
            ),
            budget_bytes,
        )
        response = SnapshotResponse(ts=ts, groups=groups, meta=None)
        # Model normalization can add fields or change numeric encodings. Bound
        # both FastAPI's Pydantic fast path and its compact JSONResponse path.
        # This final REST check fails closed with 503; it does not refit groups.
        final_size = max(
            len(response.model_dump_json().encode("utf-8")),
            len(compact_json(response.model_dump(mode="json")).encode("utf-8")),
        )
        enforce_snapshot_budget(final_size, budget_bytes)
    except SnapshotBudgetExceeded:
        raise ApiError(
            code="INTERNAL_ERROR", message="Internal server error", status_code=503
        ) from None
    return response


@router.get("/history", response_model=HistoryResponse)
async def history(
    group: Annotated[str, Query(..., min_length=1, max_length=64)],
    from_ts: Annotated[int, Query(..., ge=0, alias="from")],
    to_ts: Annotated[int, Query(..., ge=0, alias="to")],
    settings: Annotated[Settings, Depends(get_settings)],
    history_store: Annotated[HistoryStore, Depends(get_history_store)],
) -> HistoryResponse:
    """Return a historical scalar series."""
    if group not in ALLOWED_GROUPS:
        raise ApiError(code="INVALID_QUERY", message="Unknown metric group", status_code=400)
    if to_ts <= from_ts:
        raise ApiError(code="INVALID_QUERY", message="Invalid time range", status_code=400)

    window_ms = to_ts - from_ts
    if window_ms > settings.history_max_seconds * 1000:
        raise ApiError(
            code="INVALID_QUERY", message="History window exceeds retention", status_code=400
        )

    window_seconds = int(window_ms / 1000)
    limit = max(1, int(window_ms / (settings.sample_interval_seconds * 1000)))
    snapshots = await history_store.query(window_seconds=window_seconds, limit=limit)

    points: list[HistoryPoint] = []
    for snap in snapshots:
        if group == "cpu":
            if isinstance(snap.cpu, Ok):
                value = snap.cpu.value.cpu_total.value
            else:
                continue
        elif group == "memory":
            if isinstance(snap.memory, Ok):
                value = snap.memory.value.used_percent.value
            else:
                continue
        else:
            continue
        ts_val = int(snap.timestamp_utc.moment.timestamp() * 1000)
        points.append(HistoryPoint(ts=ts_val, value=value))

    points.sort(key=lambda point: point.ts)
    return HistoryResponse(group=group, points=points)
