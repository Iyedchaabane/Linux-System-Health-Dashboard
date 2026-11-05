"""Contract regression tests for the shared snapshot envelope fixtures.

``contracts/ws/v1/fixtures/envelope/`` holds a genuine ``serialize_snapshot``
output plus mutated copies: one whose ``data.type`` was changed to ``"pong"``,
one with ``data.type`` removed, and a ping carrying snapshot-only fields. The
published static schema declares ``snapshotData.type`` as ``{"const":
"snapshot"}`` and requires it, so real server output now validates against the
published schema and the mutated copies must be rejected.

Both validators must agree: Pydantic (the models the server actually uses) and
the published JSON Schema (what clients generate from).
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from monitor.domain.entities import (
    CpuSnapshot,
    DiskUsage,
    MemorySnapshot,
    NetCounters,
    ProcessInfo,
    ProcessList,
    SystemSnapshot,
)
from monitor.domain.types import MetricResult, Ok
from monitor.domain.values import (
    Bytes,
    LoadAverage,
    MonotonicTimestamp,
    Percent,
    SwapUsage,
    UtcTimestamp,
)
from monitor.presentation.ws.protocol import PingData, ServerMessage, SnapshotData
from monitor.presentation.ws.snapshot import serialize_snapshot

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_DIR = REPO_ROOT / "contracts" / "ws" / "v1"
SCHEMA_PATH = CONTRACTS_DIR / "schemas" / "server_message.schema.json"
FIXTURES_DIR = CONTRACTS_DIR / "fixtures"
ENVELOPE_DIR = FIXTURES_DIR / "envelope"

VALID_ENVELOPE_PATH = ENVELOPE_DIR / "valid_snapshot_envelope.json"
INVALID_ENVELOPE_PATH = ENVELOPE_DIR / "invalid_snapshot_envelope_discriminator.json"
MISSING_DISCRIMINATOR_PATH = ENVELOPE_DIR / "invalid_snapshot_envelope_missing_discriminator.json"
PING_WITH_SNAPSHOT_FIELDS_PATH = ENVELOPE_DIR / "invalid_ping_with_snapshot_fields.json"
VALID_PING_PATHS = (
    ENVELOPE_DIR / "valid_ping_empty_data.json",
    ENVELOPE_DIR / "valid_ping_with_type.json",
)
PING_FIXTURE_IDS = [path.name for path in VALID_PING_PATHS]

# The three published root snapshot fixtures must agree with the published schema.
ROOT_SNAPSHOT_PATHS = (
    FIXTURES_DIR / "snapshot_ok.json",
    FIXTURES_DIR / "snapshot_partial.json",
    FIXTURES_DIR / "snapshot_unavailable.json",
)
ROOT_SNAPSHOT_IDS = [path.name for path in ROOT_SNAPSHOT_PATHS]

STATIC_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
SCHEMA_VALIDATOR = jsonschema.Draft202012Validator(STATIC_SCHEMA)


def _load(path: Path) -> Any:
    """Load one shared fixture payload."""
    return json.loads(path.read_text(encoding="utf-8"))


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


def _ok_disk() -> DiskUsage:
    return DiskUsage(
        device="/", total=Bytes(value=1024), used=Bytes(value=512), percent=Percent(value=50.0)
    )


def _ok_network() -> NetCounters:
    return NetCounters(
        rx_bytes=Bytes(value=1000),
        tx_bytes=Bytes(value=500),
        sampled_at=MonotonicTimestamp(seconds=1.0),
    )


def _ok_processes() -> MetricResult[ProcessList]:
    """The two deterministic rows carried by the shared envelope fixture."""
    return Ok(
        ProcessList(
            items=(
                ProcessInfo(pid=1, name="systemd", cpu_percent=0.5, memory_rss_bytes=1048576),
                ProcessInfo(pid=42, name="bash", cpu_percent=12.25, memory_rss_bytes=2097152),
            ),
            skipped=0,
            total=2,
        )
    )


def _fixture_snapshot() -> SystemSnapshot:
    """Rebuild exactly the snapshot the shared envelope fixture was generated from."""
    return SystemSnapshot(
        cpu=Ok(_ok_cpu()),
        memory=Ok(_ok_memory()),
        disk=Ok(_ok_disk()),
        network=Ok(_ok_network()),
        timestamp_monotonic=MonotonicTimestamp(seconds=1.0),
        timestamp_utc=UtcTimestamp(moment=datetime.fromtimestamp(1.0, tz=UTC)),
        processes=_ok_processes(),
    )


def _serialized(seq: int = 1, dropped: int = 0) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        serialize_snapshot(_fixture_snapshot(), seq=seq, dropped=dropped)
    )
    return payload


def test_real_serializer_output_matches_the_valid_envelope_fixture() -> None:
    """The fixture is genuine server output, not a hand-written approximation."""
    assert _serialized(seq=1, dropped=0) == _load(VALID_ENVELOPE_PATH)


def test_serialized_envelope_carries_the_discriminator_and_drop_counter() -> None:
    """``data.type`` is always ``"snapshot"``; ``data.meta`` is never null."""
    payload = _serialized(seq=1, dropped=0)
    data = payload["data"]
    assert data["type"] == "snapshot"
    assert data["meta"] == {"dropped_since_last": 0}

    dropped = _serialized(seq=2, dropped=5)
    assert dropped["data"]["type"] == "snapshot"
    assert dropped["data"]["meta"] == {"dropped_since_last": 5}


def test_published_schema_pins_the_snapshot_discriminator() -> None:
    """The approved schema correction requires ``data.type`` and forbids extras."""
    snapshot_data = STATIC_SCHEMA["$defs"]["snapshotData"]

    assert snapshot_data["required"] == ["type", "groups"]
    assert snapshot_data["properties"]["type"] == {"const": "snapshot"}
    assert snapshot_data["additionalProperties"] is False


def test_published_schema_pins_the_ping_data() -> None:
    """The approved ping correction makes ``data.type`` optional and forbids extras."""
    ping_data = STATIC_SCHEMA["$defs"]["pingData"]

    assert ping_data["required"] == []
    assert ping_data["properties"]["type"] == {"const": "ping"}
    assert ping_data["additionalProperties"] is False


def test_valid_envelope_fixture_is_accepted_by_pydantic_and_schema() -> None:
    """Real server output is valid for both validators."""
    payload = _load(VALID_ENVELOPE_PATH)

    message = ServerMessage.model_validate(payload)

    assert isinstance(message.data, SnapshotData)
    assert SCHEMA_VALIDATOR.is_valid(payload)


def test_invalid_envelope_fixture_is_rejected_by_pydantic_and_schema() -> None:
    """A wrong discriminator is rejected, not silently coerced."""
    payload = _load(INVALID_ENVELOPE_PATH)

    with pytest.raises(ValidationError):
        ServerMessage.model_validate(payload)
    assert not SCHEMA_VALIDATOR.is_valid(payload)


def test_invalid_envelope_differs_from_valid_only_at_the_discriminator() -> None:
    """The rejection is attributable to ``data.type`` alone."""
    valid = _load(VALID_ENVELOPE_PATH)
    invalid = _load(INVALID_ENVELOPE_PATH)

    assert invalid["data"]["type"] != valid["data"]["type"]

    repaired = copy.deepcopy(invalid)
    repaired["data"]["type"] = valid["data"]["type"]

    assert repaired == valid


@pytest.mark.parametrize("path", ROOT_SNAPSHOT_PATHS, ids=ROOT_SNAPSHOT_IDS)
def test_published_root_snapshot_fixture_conforms_to_pydantic_and_schema(path: Path) -> None:
    """Published fixtures no longer contradict the published schema."""
    payload = _load(path)

    message = ServerMessage.model_validate(payload)

    assert isinstance(message.data, SnapshotData)
    assert SCHEMA_VALIDATOR.is_valid(payload)


def test_snapshot_envelope_without_discriminator_is_rejected_by_pydantic_and_schema() -> None:
    """The required ``data.type`` is no longer defaulted on either side."""
    payload = _load(MISSING_DISCRIMINATOR_PATH)

    with pytest.raises(ValidationError):
        ServerMessage.model_validate(payload)
    assert not SCHEMA_VALIDATOR.is_valid(payload)


def test_missing_discriminator_fixture_differs_from_valid_only_by_the_absent_key() -> None:
    """The rejection is attributable to the absent ``data.type`` alone."""
    valid = _load(VALID_ENVELOPE_PATH)
    invalid = _load(MISSING_DISCRIMINATOR_PATH)

    assert "type" not in invalid["data"]
    assert "type" in valid["data"]

    repaired = copy.deepcopy(invalid)
    repaired["data"]["type"] = valid["data"]["type"]

    assert repaired == valid


@pytest.mark.parametrize("path", VALID_PING_PATHS, ids=PING_FIXTURE_IDS)
def test_valid_ping_fixture_is_accepted_by_pydantic_and_schema(path: Path) -> None:
    """Both published ping fixtures validate against Pydantic and the published schema."""
    payload = _load(path)

    message = ServerMessage.model_validate(payload)

    assert isinstance(message.data, PingData)
    assert message.data.type == "ping"
    assert SCHEMA_VALIDATOR.is_valid(payload)


def test_ping_with_snapshot_fields_is_rejected_by_pydantic_and_schema() -> None:
    """``PingData`` forbids extras, so a ping cannot smuggle snapshot fields."""
    payload = _load(PING_WITH_SNAPSHOT_FIELDS_PATH)

    with pytest.raises(ValidationError):
        ServerMessage.model_validate(payload)
    # ``pingData`` is ``{"additionalProperties": false, "required": [], "properties":
    # {"type": {"const": "ping"}}}``, so an empty ping data or ``{"type": "ping"}`` is
    # accepted, but snapshot-only fields are forbidden extras; the rejection is attributable
    # to those extras and comes from the Pydantic assertion above.
    assert not SCHEMA_VALIDATOR.is_valid(payload)


def test_valid_ping_resolves_to_ping_data_model() -> None:
    """The server model accepts the minimal ping payload and dispatches to ``PingData``.

    The published ``pingData`` schema declares ``required: []`` and
    ``properties: {"type": {"const": "ping"}}`` with ``additionalProperties: false``,
    so both an empty ``data`` object and ``{"type": "ping"}`` are valid pings.
    """
    for data in ({}, {"type": "ping"}):
        payload = {"v": 1, "type": "ping", "seq": 3, "ts": 1000, "data": data}

        message = ServerMessage.model_validate(payload)

        assert isinstance(message.data, PingData)
        assert message.data.type == "ping"
