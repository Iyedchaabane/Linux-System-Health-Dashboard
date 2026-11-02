"""REST API schemas for the Linux System Health Dashboard."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from monitor.presentation.ws.protocol import GroupState, SnapshotMeta

__all__ = ["GroupState", "HealthResponse", "HistoryPoint", "HistoryResponse", "SnapshotResponse"]


class SnapshotResponse(BaseModel):
    """REST snapshot response mirroring the WebSocket v1 snapshot payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ts: int = Field(ge=0, strict=True)
    groups: dict[str, GroupState]
    meta: SnapshotMeta | None = None


class HistoryPoint(BaseModel):
    """One historical scalar sample."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ts: int = Field(ge=0, strict=True)
    value: float = Field(strict=True)


class HistoryResponse(BaseModel):
    """REST historical scalar series response."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    group: str
    points: list[HistoryPoint]


class HealthResponse(BaseModel):
    """Health and readiness response."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["ok"]


class ErrorDetail(BaseModel):
    """Canonical API error detail."""

    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    """Canonical API error envelope."""

    error: ErrorDetail
