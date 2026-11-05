"""WebSocket v1 protocol models for the Linux System Health Dashboard."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    GetJsonSchemaHandler,
    GetPydanticSchema,
    TypeAdapter,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from monitor.domain.types import UnavailableKind

PROTOCOL_VERSION: int = 1


class ServerMessageType(StrEnum):
    """Server-to-client WebSocket message types."""

    HELLO = "hello"
    SNAPSHOT = "snapshot"
    ERROR = "error"
    PING = "ping"
    BYE = "bye"


class ClientMessageType(StrEnum):
    """Client-to-server WebSocket message types."""

    SUBSCRIBE = "subscribe"
    PONG = "pong"
    PING = "ping"


class HelloLimits(BaseModel):
    """Connection and rate limits advertised in the hello message."""

    max_clients: int = Field(ge=1, strict=True)
    max_clients_per_ip: int = Field(ge=1, strict=True)
    max_message_bytes: int = Field(ge=1, strict=True)
    rate_limit_burst: int = Field(ge=1, strict=True)
    rate_limit_refill_per_second: float = Field(ge=0.0, le=100.0)
    send_timeout_seconds: float = Field(ge=0.5, le=30.0)
    handshake_timeout_seconds: float = Field(ge=0.5, le=30.0)


class HelloData(BaseModel):
    """Hello payload."""

    type: Literal["hello"] = "hello"
    interval_ms: int = Field(ge=100, le=10_000)
    max_message_bytes: int = Field(ge=1)
    groups: list[str] = Field(default_factory=list)
    server_time: float = Field(ge=0.0)
    limits: HelloLimits


class ByeData(BaseModel):
    """Bye payload."""

    type: Literal["bye"] = "bye"
    reason: str = Field(min_length=1, max_length=123)


class ErrorData(BaseModel):
    """Error payload."""

    type: Literal["error"] = "error"
    code: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=512)


class PingData(BaseModel):
    """Ping payload; unknown extra fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["ping"] = "ping"


class GroupStateOk(BaseModel):
    """Ok group state."""

    status: Literal["ok"] = "ok"
    value: dict[str, Any] | None = None
    partial: bool = False


class GroupStateUnavailable(BaseModel):
    """Unavailable group state."""

    status: Literal["unavailable"]
    kind: UnavailableKind
    reason: str = Field(min_length=1, max_length=512)


GroupState: TypeAlias = Annotated[
    GroupStateOk | GroupStateUnavailable, Field(discriminator="status")
]


class ProcessRow(BaseModel):
    """One namespace-visible process; 100% CPU means one logical CPU."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pid: int = Field(gt=0, strict=True)
    name: str = Field(max_length=128, strict=True)
    cpu_percent: Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)] | None
    memory_rss_bytes: int = Field(ge=0, strict=True)


class ProcessesValue(BaseModel):
    """Bounded current process list, not a historical series.

    ``total`` counts readable processes in the same sample before top-N
    truncation, so it is at least ``len(items)``; ``skipped`` stays separate.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: list[ProcessRow]
    skipped: int = Field(ge=0, strict=True)
    total: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def _total_covers_items(self) -> ProcessesValue:
        """Reject a total that cannot account for the returned rows."""
        if self.total < len(self.items):
            raise ValueError("total must be greater than or equal to len(items)")
        return self


class ProcessesStateOk(BaseModel):
    """Typed successful processes group."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["ok"]
    partial: bool = Field(strict=True)
    value: ProcessesValue


ProcessesState: TypeAlias = Annotated[
    ProcessesStateOk | GroupStateUnavailable, Field(discriminator="status")
]
_processes_adapter = TypeAdapter(ProcessesState)


def _validate_processes_group(value: Any) -> Any:
    """Validate the named group without changing existing dictionary consumers."""
    if isinstance(value, dict) and "processes" in value:
        group = value["processes"]
        if isinstance(group, BaseModel):
            group = group.model_dump()
        _processes_adapter.validate_python(group)
    return value


def _groups_json_schema(schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
    result = handler(schema)
    result["properties"] = {"processes": handler(_processes_adapter.core_schema)}
    return result


SnapshotGroups: TypeAlias = Annotated[
    dict[str, GroupState],
    BeforeValidator(_validate_processes_group),
    GetPydanticSchema(get_pydantic_json_schema=_groups_json_schema),
]


class SnapshotMeta(BaseModel):
    """Snapshot metadata."""

    dropped_since_last: int | None = Field(default=None, ge=0, strict=True)


class SnapshotData(BaseModel):
    """Snapshot payload."""

    type: Literal["snapshot"]
    groups: SnapshotGroups = Field(default_factory=dict)
    meta: SnapshotMeta | None = None


ServerMessageData: TypeAlias = HelloData | SnapshotData | ErrorData | PingData | ByeData


class ServerMessage(BaseModel):
    """Server-to-client WebSocket v1 message."""

    model_config = ConfigDict(extra="forbid")
    v: Literal[1]
    type: ServerMessageType
    seq: int = Field(ge=0, strict=True)
    ts: int = Field(ge=0, strict=True)
    data: ServerMessageData

    @field_validator("data", mode="before")
    @classmethod
    def validate_processes_payload(cls, value: Any, info: ValidationInfo) -> Any:
        """Prevent the legacy payload union from bypassing processes validation."""
        if info.data.get("type") == ServerMessageType.SNAPSHOT and isinstance(value, dict):
            _validate_processes_group(value.get("groups"))
        return value


class ClientSubscribeData(BaseModel):
    """Subscribe payload."""

    type: Literal["subscribe"] = "subscribe"
    groups: list[str] = Field(min_length=1)


class ClientPongData(BaseModel):
    """Pong payload."""

    type: Literal["pong"] = "pong"


class ClientPingData(BaseModel):
    """Client ping payload."""

    type: Literal["ping"] = "ping"


ClientMessageData: TypeAlias = ClientSubscribeData | ClientPongData | ClientPingData


class ClientMessage(BaseModel):
    """Client-to-server WebSocket v1 message."""

    model_config = ConfigDict(extra="forbid")
    v: Literal[1]
    type: ClientMessageType
    seq: int = Field(ge=0, strict=True)
    ts: int = Field(ge=0, strict=True)
    data: ClientMessageData


def parse_server_message(raw: dict[str, Any]) -> ServerMessage:
    """Validate and parse a server message."""
    return ServerMessage.model_validate(raw)


def parse_client_message(raw: dict[str, Any]) -> ClientMessage:
    """Validate and parse a client message."""
    return ClientMessage.model_validate(raw)
