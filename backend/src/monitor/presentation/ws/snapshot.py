"""Serialize SystemSnapshot into the WebSocket v1 snapshot message."""

from __future__ import annotations

from typing import Any

from monitor.domain.entities import (
    CpuSnapshot,
    DiskUsage,
    MemorySnapshot,
    NetCounters,
    ProcessList,
    SystemSnapshot,
)
from monitor.domain.types import MetricResult, Ok, Unavailable
from monitor.presentation.ws.protocol import (
    GroupStateOk,
    GroupStateUnavailable,
    ProcessesStateOk,
    ProcessesValue,
    ProcessRow,
    ServerMessage,
    ServerMessageType,
    SnapshotData,
    SnapshotMeta,
)


def _map_cpu_result(result: MetricResult[CpuSnapshot]) -> object:
    """Map a CPU MetricResult onto the WebSocket v1 group-state contract."""
    if isinstance(result, Ok):
        value = result.value
        return GroupStateOk(
            status="ok",
            value={
                "cpu_total": value.cpu_total.value,
                "per_core": [p.value if p is not None else None for p in value.per_core],
                "load_average": value.load_average.value,
                "core_count": value.core_count,
                "frequency_hz": value.frequency_hz,
            },
            partial=result.partial,
        )
    if isinstance(result, Unavailable):
        return GroupStateUnavailable(
            status="unavailable",
            kind=result.kind,
            reason=result.reason,
        )
    raise TypeError(f"Unsupported MetricResult: {type(result)!r}")


def _map_memory_result(result: MetricResult[MemorySnapshot]) -> object:
    """Map a memory MetricResult onto the WebSocket v1 group-state contract."""
    if isinstance(result, Ok):
        value = result.value
        return GroupStateOk(
            status="ok",
            value={
                "total": value.total.value,
                "available": value.available.value,
                "used_percent": value.used_percent.value,
            },
            partial=result.partial,
        )
    if isinstance(result, Unavailable):
        return GroupStateUnavailable(
            status="unavailable",
            kind=result.kind,
            reason=result.reason,
        )
    raise TypeError(f"Unsupported MetricResult: {type(result)!r}")


def _map_disk_result(result: MetricResult[DiskUsage]) -> object:
    """Map a DiskUsage MetricResult onto the WebSocket v1 group-state contract."""
    if isinstance(result, Ok):
        value = result.value
        return GroupStateOk(
            status="ok",
            value={
                "device": value.device,
                "total": value.total.value,
                "used": value.used.value,
                "percent": value.percent.value,
            },
            partial=result.partial,
        )
    if isinstance(result, Unavailable):
        return GroupStateUnavailable(
            status="unavailable",
            kind=result.kind,
            reason=result.reason,
        )
    raise TypeError(f"Unsupported MetricResult: {type(result)!r}")


def _map_network_result(result: MetricResult[NetCounters]) -> object:
    """Map a network MetricResult onto the WebSocket v1 group-state contract."""
    if isinstance(result, Ok):
        value = result.value
        return GroupStateOk(
            status="ok",
            value={
                "rx_bytes": value.rx_bytes.value,
                "tx_bytes": value.tx_bytes.value,
            },
            partial=result.partial,
        )
    if isinstance(result, Unavailable):
        return GroupStateUnavailable(
            status="unavailable",
            kind=result.kind,
            reason=result.reason,
        )
    raise TypeError(f"Unsupported MetricResult: {type(result)!r}")


def _map_processes_result(
    result: MetricResult[ProcessList],
) -> ProcessesStateOk | GroupStateUnavailable:
    """Map a ProcessList MetricResult onto the WebSocket v1 processes group.

    Rows keep the collector's order, cap and values: nothing is re-sorted,
    re-truncated, renamed or clamped, and ``cpu_percent=None`` stays ``None``.
    """
    if isinstance(result, Ok):
        value = result.value
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
                    for item in value.items
                ],
                skipped=value.skipped,
                total=value.total,
            ),
        )
    if isinstance(result, Unavailable):
        return GroupStateUnavailable(
            status="unavailable",
            kind=result.kind,
            reason=result.reason,
        )
    raise TypeError(f"Unsupported MetricResult: {type(result)!r}")


def serialize_snapshot(snapshot: SystemSnapshot, seq: int = 0, dropped: int = 0) -> str:
    """Serialize a SystemSnapshot into a WebSocket v1 snapshot JSON string.

    Args:
        snapshot: The SystemSnapshot to serialize.

    Returns:
        JSON string of the serialized snapshot message.
    """
    # Build the groups dict with proper protocol-state typing
    groups: dict[str, GroupStateOk | GroupStateUnavailable] = {}
    cpu_state = _map_cpu_result(snapshot.cpu)
    if isinstance(cpu_state, (GroupStateOk, GroupStateUnavailable)):
        groups["cpu"] = cpu_state
    memory_state = _map_memory_result(snapshot.memory)
    if isinstance(memory_state, (GroupStateOk, GroupStateUnavailable)):
        groups["memory"] = memory_state
    disk_state = _map_disk_result(snapshot.disk)
    if isinstance(disk_state, (GroupStateOk, GroupStateUnavailable)):
        groups["disk"] = disk_state
    network_state = _map_network_result(snapshot.network)
    if isinstance(network_state, (GroupStateOk, GroupStateUnavailable)):
        groups["network"] = network_state

    # The protocol's declared group alias covers the four legacy groups only;
    # the processes entry travels as its validated JSON shape and is checked by
    # SnapshotGroups. Omitted entirely when the snapshot carries no result.
    groups_payload: dict[str, Any] = dict(groups)
    if snapshot.processes is not None:
        groups_payload["processes"] = _map_processes_result(snapshot.processes).model_dump(
            mode="json"
        )

    ts_ms = int(snapshot.timestamp_utc.moment.timestamp() * 1000)

    # Use a unvalidated dict during construction to assemble the data payload
    msg = ServerMessage(
        v=1,
        type=ServerMessageType.SNAPSHOT,
        seq=seq,
        ts=ts_ms,
        data=SnapshotData(
            type="snapshot",
            groups=groups_payload,
            meta=SnapshotMeta(dropped_since_last=dropped),
        ),
    )
    return msg.model_dump_json()
