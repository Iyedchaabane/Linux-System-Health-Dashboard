"""Contract regression tests for the shared ``processes`` group fixtures.

The 14 fixtures in ``contracts/ws/v1/fixtures/processes/`` cover the shape of the
``processes`` snapshot group only. They carry the real ``data.type: "snapshot"``
discriminator, which the published static schema now requires, so real server
output validates against the published schema.

Every fixture must receive the same verdict from Pydantic (the models the server
actually uses) and from the published JSON Schema (what clients generate from).
"""

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from monitor.presentation.ws.protocol import ServerMessage, SnapshotData

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = REPO_ROOT / "contracts" / "ws" / "v1" / "fixtures" / "processes"
SCHEMA_PATH = REPO_ROOT / "contracts" / "ws" / "v1" / "schemas" / "server_message.schema.json"

# The exact expected inventory: a deleted, renamed or added fixture must fail loudly.
EXPECTED_FIXTURES = frozenset(
    {
        "invalid_processes_name_129.json",
        "invalid_processes_negative_cpu.json",
        "invalid_processes_negative_rss.json",
        "invalid_processes_negative_skipped.json",
        "invalid_processes_pid_zero.json",
        "invalid_processes_wrong_name_type.json",
        "invalid_processes_wrong_pid_type.json",
        "valid_processes_cpu_over_100.json",
        "valid_processes_empty_list.json",
        "valid_processes_empty_name.json",
        "valid_processes_name_128_codepoints.json",
        "valid_processes_normal.json",
        "valid_processes_null_cpu.json",
        "valid_processes_partial_skipped.json",
    }
)

FIXTURE_PATHS = sorted(FIXTURES_DIR.glob("*.json"))
FIXTURE_IDS = [path.name for path in FIXTURE_PATHS]

STATIC_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
SCHEMA_VALIDATOR = jsonschema.Draft202012Validator(STATIC_SCHEMA)


def _load(path: Path) -> Any:
    """Load one shared fixture payload."""
    return json.loads(path.read_text(encoding="utf-8"))


def _expected_verdict(name: str) -> bool:
    """The filename prefix is the contract: ``valid_`` must be accepted."""
    return name.startswith("valid_")


def _longest_process_name(path: Path) -> str:
    """Return the longest process name carried by a fixture."""
    items = _load(path)["data"]["groups"]["processes"]["value"]["items"]
    assert items
    return max((str(item["name"]) for item in items), key=len)


def test_fixture_inventory_matches_expected_names() -> None:
    """Exactly the approved 14 fixtures exist, split 7 accepted and 7 rejected."""
    assert set(FIXTURE_IDS) == EXPECTED_FIXTURES
    assert len(FIXTURE_IDS) == 14
    assert sum(name.startswith("valid_") for name in FIXTURE_IDS) == 7
    assert sum(name.startswith("invalid_") for name in FIXTURE_IDS) == 7


@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=FIXTURE_IDS)
def test_pydantic_and_json_schema_agree_with_filename_prefix(path: Path) -> None:
    """Both validators must reach the verdict the fixture filename promises."""
    payload = _load(path)
    expected = _expected_verdict(path.name)

    message: ServerMessage | None = None
    try:
        message = ServerMessage.model_validate(payload)
    except ValidationError as error:
        pydantic_valid = False
        pydantic_error = f"{error.error_count()} validation error(s): {error.errors()[0]['msg']}"
    else:
        pydantic_valid = True
        pydantic_error = "none"

    schema_valid = SCHEMA_VALIDATOR.is_valid(payload)

    assert pydantic_valid is expected, (
        f"{path.name}: Pydantic verdict {pydantic_valid} disagrees with the "
        f"{'valid' if expected else 'invalid'} filename prefix ({pydantic_error})"
    )
    if expected:
        # ``ServerMessageData`` is not a discriminated union, so "accepted" must
        # also mean "resolved to the snapshot model". A snapshot-shaped payload
        # cannot pass as ``PingData``: that model requires ``type: "ping"`` and
        # forbids extra fields.
        assert message is not None
        assert isinstance(message.data, SnapshotData), (
            f"{path.name}: accepted as {type(message.data).__name__}, not SnapshotData"
        )
    assert schema_valid is expected, (
        f"{path.name}: JSON Schema verdict {schema_valid} disagrees with the "
        f"{'valid' if expected else 'invalid'} filename prefix"
    )
    assert pydantic_valid is schema_valid, (
        f"{path.name}: Pydantic ({pydantic_valid}) and JSON Schema ({schema_valid}) disagree"
    )


def test_process_name_boundary_counts_unicode_code_points() -> None:
    """The 128 limit counts code points, not UTF-16 units."""
    accepted_name = _longest_process_name(FIXTURES_DIR / "valid_processes_name_128_codepoints.json")
    rejected_name = _longest_process_name(FIXTURES_DIR / "invalid_processes_name_129.json")

    assert len(accepted_name) == 128
    assert len(accepted_name.encode("utf-16-le")) // 2 > 128
    assert len(rejected_name) == 129


def test_total_is_required_and_non_negative_in_both_validators() -> None:
    """A copy of a valid payload without a usable ``total`` is rejected twice."""
    payload = _load(FIXTURES_DIR / "valid_processes_normal.json")

    missing = copy.deepcopy(payload)
    del missing["data"]["groups"]["processes"]["value"]["total"]
    negative = copy.deepcopy(payload)
    negative["data"]["groups"]["processes"]["value"]["total"] = -1

    for broken in (missing, negative):
        with pytest.raises(ValidationError):
            ServerMessage.model_validate(broken)
        assert not SCHEMA_VALIDATOR.is_valid(broken)
