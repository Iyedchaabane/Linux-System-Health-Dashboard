"""WebSocket v1 protocol models for the Linux System Health Dashboard."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

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
    """Ping payload."""

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


class SnapshotMeta(BaseModel):
    """Snapshot metadata."""

    dropped_since_last: int | None = Field(default=None, ge=0, strict=True)


class SnapshotData(BaseModel):
    """Snapshot payload."""

    type: Literal["snapshot"] = "snapshot"
    groups: dict[str, GroupState] = Field(default_factory=dict)
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
