"""Contract tests for the WebSocket v1 protocol and shared fixtures."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from monitor.domain.types import UnavailableKind
from monitor.presentation.ws.protocol import (
    ByeData,
    ClientMessage,
    ClientMessageType,
    ClientSubscribeData,
    ErrorData,
    GroupStateOk,
    GroupStateUnavailable,
    HelloData,
    ServerMessage,
    ServerMessageType,
    SnapshotData,
)

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "contracts" / "ws" / "v1" / "fixtures"


def _load(name: str) -> dict:
    """Load a shared WebSocket fixture from the contract fixtures directory."""
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.integration
def test_hello_fixture_validates() -> None:
    """The hello fixture validates and carries the approved defaults."""
    message = ServerMessage.model_validate(_load("hello"))
    assert message.type is ServerMessageType.HELLO
    assert message.v == 1
    assert message.seq == 0
    assert isinstance(message.data, HelloData)
    assert message.data.interval_ms == 1000
    assert message.data.groups == ["cpu", "memory"]
    assert message.data.limits.max_clients == 100


@pytest.mark.integration
def test_snapshot_ok_fixture_validates() -> None:
    """The ok snapshot fixture validates with ok groups."""
    message = ServerMessage.model_validate(_load("snapshot_ok"))
    assert message.type is ServerMessageType.SNAPSHOT
    assert isinstance(message.data, SnapshotData)
    assert "cpu" in message.data.groups
    assert "memory" in message.data.groups
    cpu = message.data.groups["cpu"]
    assert isinstance(cpu, GroupStateOk)
    assert cpu.partial is False


@pytest.mark.integration
def test_snapshot_partial_fixture_validates() -> None:
    """The partial snapshot fixture validates with a partial cpu group."""
    message = ServerMessage.model_validate(_load("snapshot_partial"))
    assert message.type is ServerMessageType.SNAPSHOT
    assert isinstance(message.data, SnapshotData)
    cpu = message.data.groups["cpu"]
    assert isinstance(cpu, GroupStateOk)
    assert cpu.partial is True


@pytest.mark.integration
def test_snapshot_unavailable_fixture_validates() -> None:
    """The unavailable snapshot fixture validates with an unavailable cpu group."""
    message = ServerMessage.model_validate(_load("snapshot_unavailable"))
    assert message.type is ServerMessageType.SNAPSHOT
    assert isinstance(message.data, SnapshotData)
    cpu = message.data.groups["cpu"]
    assert isinstance(cpu, GroupStateUnavailable)
    assert cpu.kind is UnavailableKind.PERMISSION
    memory = message.data.groups["memory"]
    assert isinstance(memory, GroupStateOk)


@pytest.mark.integration
def test_error_fixture_validates() -> None:
    """The error fixture validates with a safe error payload."""
    message = ServerMessage.model_validate(_load("error_invalid_message"))
    assert message.type is ServerMessageType.ERROR
    assert isinstance(message.data, ErrorData)
    assert message.data.code == "INVALID_MESSAGE"


@pytest.mark.integration
def test_bye_fixture_validates() -> None:
    """The bye fixture validates with a safe close reason."""
    message = ServerMessage.model_validate(_load("bye"))
    assert message.type is ServerMessageType.BYE
    assert isinstance(message.data, ByeData)
    assert message.data.reason == "shutdown"


@pytest.mark.integration
def test_client_subscribe_message_validates() -> None:
    """The client subscribe message validates."""
    subscribe = ClientMessage.model_validate(
        {
            "v": 1,
            "type": "subscribe",
            "seq": 1,
            "ts": 1767225601500,
            "data": {"groups": ["cpu", "memory"]},
        }
    )
    assert subscribe.type is ClientMessageType.SUBSCRIBE
    assert isinstance(subscribe.data, ClientSubscribeData)
    assert subscribe.data.groups == ["cpu", "memory"]


@pytest.mark.integration
def test_server_message_version_mismatch_is_rejected() -> None:
    """A server message with an unsupported version must fail validation."""
    with pytest.raises(ValidationError):
        ServerMessage.model_validate(
            {
                "v": 2,
                "type": "hello",
                "seq": 0,
                "ts": 1767225600512,
                "data": {
                    "interval_ms": 1000,
                    "max_message_bytes": 16384,
                    "groups": ["cpu", "memory"],
                    "server_time": 1767225600.512,
                    "limits": {
                        "max_clients": 100,
                        "max_clients_per_ip": 10,
                        "max_message_bytes": 4096,
                        "rate_limit_burst": 10,
                        "rate_limit_refill_per_second": 2.0,
                        "send_timeout_seconds": 5.0,
                        "handshake_timeout_seconds": 5.0,
                    },
                },
            }
        )


@pytest.mark.integration
def test_unknown_server_message_type_is_rejected() -> None:
    """An unknown server message type must fail validation."""
    with pytest.raises(ValidationError):
        ServerMessage.model_validate(
            {
                "v": 1,
                "type": "unknown",
                "seq": 0,
                "ts": 1767225600512,
                "data": {"interval_ms": 1000},
            }
        )


@pytest.mark.integration
def test_websocket_contract_fixtures_are_valid_json() -> None:
    """Committed WebSocket contract fixtures must be valid JSON with expected keys."""
    for name in (
        "hello",
        "snapshot_ok",
        "snapshot_partial",
        "snapshot_unavailable",
        "error_invalid_message",
        "bye",
    ):
        fixture = json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))
        assert fixture["v"] == 1
        assert fixture["type"] in ("hello", "snapshot", "error", "bye")
