"""Deterministic unit coverage for the snapshot size-budget guard.

The guard is the single production policy shared by the WebSocket stream and
the REST snapshot route: whole groups are replaced by an unavailable state,
largest encoded contribution first, ties by group name, one pass, stopping at
the first fit. These tests drive the guard directly and through the WebSocket
write boundary so the policy, its warning and the snapshot-only scope stay
regression-tested without depending on host metrics or wall-clock time.
"""

import json
import logging
from typing import Any, cast

import pytest
from pydantic import ValidationError
from starlette.websockets import WebSocket

from monitor.config.settings import Settings
from monitor.presentation.ws import budget as budget_module
from monitor.presentation.ws.budget import (
    DEFAULT_SNAPSHOT_BUDGET_BYTES,
    DEGRADED_REASON,
    SnapshotBudgetExceeded,
    compact_json,
    fit_snapshot_to_budget,
)
from monitor.presentation.ws.endpoint import _OutboundMessages
from monitor.presentation.ws.hub import BroadcastHub
from monitor.presentation.ws.protocol import (
    ErrorData,
    ProcessesStateOk,
    ProcessesValue,
    ProcessRow,
    ServerMessage,
    ServerMessageType,
)
from tests.contract.test_process_payload_budget import (
    NAMES,
    _four_groups,
    _full_message,
)

BUDGET = DEFAULT_SNAPSHOT_BUDGET_BYTES
DEGRADED_STATE = {
    "status": "unavailable",
    "kind": "transient",
    "reason": DEGRADED_REASON,
}
SENTINEL = "row-secret-7f3a"
BUDGET_LOGGER = "monitor.presentation.ws.budget"
FIXED_TS_MS = 1_767_225_600_000


def _envelope(groups: dict[str, Any]) -> str:
    """Encode the canonical WebSocket snapshot envelope around ``groups``."""
    return compact_json(
        {
            "v": 1,
            "type": "snapshot",
            "seq": 1,
            "ts": FIXED_TS_MS,
            "data": {
                "type": "snapshot",
                "groups": groups,
                "meta": {"dropped_since_last": 0},
            },
        }
    )


def _wire_size(groups: dict[str, Any]) -> int:
    return len(_envelope(groups).encode("utf-8"))


def _fit(groups: dict[str, Any], budget: int) -> str:
    return fit_snapshot_to_budget(groups, _envelope, budget)


def _clone(groups: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(groups))


def _four_group_fixture() -> dict[str, Any]:
    return {
        "cpu": {
            "status": "ok",
            "value": {
                "cpu_total": 87.125,
                "per_core": [87.125] * 64,
                "load_average": 123.456,
                "core_count": 64,
                "frequency_hz": 3_999_999_999.0,
            },
            "partial": False,
        },
        "memory": {
            "status": "ok",
            "value": {"total": 2**40, "available": 2**38, "used_percent": 75.0},
            "partial": False,
        },
        "disk": {
            "status": "ok",
            "value": {
                "device": "/dev/nvme0n1p1",
                "total": 2**48,
                "used": 2**47,
                "percent": 50.0,
            },
            "partial": False,
        },
        "network": {
            "status": "ok",
            "value": {"rx_bytes": 2**53 - 1, "tx_bytes": 2**52 + 12345},
            "partial": False,
        },
    }


def _process_names() -> list[str]:
    names: list[str] = []
    for index in range(25):
        prefix = f"{SENTINEL}-{index:02d}-"
        names.append(prefix + "x" * (128 - len(prefix)))
    return names


def _process_groups() -> dict[str, Any]:
    rows = [
        ProcessRow(
            pid=2**22 - 25 + index,
            name=name,
            cpu_percent=3210.125 - (index // 2) * 100 if index < 23 else None,
            memory_rss_bytes=2**40 + index * 4096,
        )
        for index, name in enumerate(_process_names())
    ]
    processes = ProcessesStateOk(
        status="ok", partial=True, value=ProcessesValue(items=rows, skipped=12345)
    )
    return {
        "cpu": {
            "status": "ok",
            "value": {"cpu_total": 87.125, "core_count": 64},
            "partial": False,
        },
        "processes": processes.model_dump(mode="json"),
    }


def _budget_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == BUDGET_LOGGER]


class _CapturingSocket:
    """Only the transport boundary is fake; the sender is production code."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(text)


@pytest.mark.parametrize("case", NAMES)
def test_guard_wire_gate_for_contract_payloads(case: str) -> None:
    """Every adversarial contract payload is bounded on the wire."""
    raw = _full_message(NAMES[case])
    message = json.loads(raw)
    groups = message["data"]["groups"]

    def encode(candidate: dict[str, Any]) -> str:
        message["data"]["groups"] = candidate
        return compact_json(message)

    pre_guard = len(compact_json(message).encode("utf-8"))
    text = fit_snapshot_to_budget(groups, encode, BUDGET)
    assert len(text.encode("utf-8")) <= BUDGET
    if pre_guard <= BUDGET:
        assert text == raw
        assert groups == json.loads(raw)["data"]["groups"]
    else:
        assert any(group == DEGRADED_STATE for group in groups.values())


def test_guard_wire_gate_for_high_core_payload() -> None:
    raw = _four_groups(4096)
    message = json.loads(raw)
    groups = message["data"]["groups"]

    def encode(candidate: dict[str, Any]) -> str:
        message["data"]["groups"] = candidate
        return compact_json(message)

    assert len(compact_json(message).encode("utf-8")) > BUDGET
    text = fit_snapshot_to_budget(groups, encode, BUDGET)
    assert len(text.encode("utf-8")) <= BUDGET
    assert groups["cpu"] == DEGRADED_STATE


def test_exact_fit_budget_degrades_nothing_and_one_byte_less_degrades(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=BUDGET_LOGGER)
    groups = _four_group_fixture()
    exact = _wire_size(groups)

    text = _fit(groups, exact)
    assert len(text.encode("utf-8")) == exact
    assert groups == _four_group_fixture()
    assert _budget_records(caplog) == []

    groups = _four_group_fixture()
    text = _fit(groups, exact - 1)
    assert len(text.encode("utf-8")) <= exact - 1
    assert groups["cpu"] == DEGRADED_STATE
    assert len(_budget_records(caplog)) == 1


def test_degradation_is_largest_first_and_stops_at_first_fit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=BUDGET_LOGGER)
    groups = _four_group_fixture()
    sizes = {name: len(compact_json(group).encode("utf-8")) for name, group in groups.items()}
    expected = sorted(sizes, key=lambda name: (-sizes[name], name))
    assert expected == ["cpu", "disk", "memory", "network"]

    after_one = _clone(groups)
    after_one[expected[0]] = DEGRADED_STATE
    after_two = _clone(groups)
    for name in expected[:2]:
        after_two[name] = DEGRADED_STATE
    budget = _wire_size(after_two)
    assert _wire_size(after_one) > budget

    text = _fit(groups, budget)
    assert len(text.encode("utf-8")) == budget
    assert groups[expected[0]] == DEGRADED_STATE
    assert groups[expected[1]] == DEGRADED_STATE
    assert groups[expected[2]] != DEGRADED_STATE
    assert groups[expected[3]] != DEGRADED_STATE
    records = _budget_records(caplog)
    assert len(records) == 1
    assert f"degraded={expected[:2]!r}" in records[0].getMessage()


def test_tie_break_is_by_group_name(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger=BUDGET_LOGGER)
    # ``gamma`` is inserted first, so insertion order would pick the wrong group.
    groups = {
        "gamma": {"status": "ok", "value": {"x": "a" * 200}, "partial": False},
        "alpha": {"status": "ok", "value": {"x": "a" * 200}, "partial": False},
    }
    exact = _wire_size(groups)

    text = _fit(groups, exact - 1)
    assert len(text.encode("utf-8")) <= exact - 1
    assert groups["alpha"] == DEGRADED_STATE
    assert groups["gamma"] != DEGRADED_STATE
    records = _budget_records(caplog)
    assert len(records) == 1
    assert "degraded=['alpha']" in records[0].getMessage()


def test_process_rows_are_never_truncated_or_renamed() -> None:
    groups = _process_groups()
    original = _clone(groups)

    text = _fit(groups, BUDGET)
    assert groups == original
    emitted = json.loads(text)
    assert emitted["data"]["groups"]["processes"] == original["processes"]
    rows = groups["processes"]["value"]["items"]
    assert len(rows) == 25
    assert [row["name"] for row in rows] == _process_names()
    assert [row["cpu_percent"] for row in rows] == [
        row["cpu_percent"] for row in original["processes"]["value"]["items"]
    ]


def test_process_group_is_replaced_whole_when_it_does_not_fit() -> None:
    groups = _process_groups()
    original = _clone(groups)

    text = _fit(groups, 1000)
    assert len(text.encode("utf-8")) <= 1000
    assert groups["processes"] == DEGRADED_STATE
    assert "value" not in groups["processes"]
    assert "items" not in text
    for name in _process_names():
        assert name not in text
    assert groups["cpu"] == original["cpu"]


def test_warning_is_single_and_contains_no_row_data(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=BUDGET_LOGGER)
    groups = _process_groups()
    budget = 2000

    text = _fit(groups, budget)
    final_size = len(text.encode("utf-8"))
    assert final_size <= budget
    records = _budget_records(caplog)
    assert len(records) == 1
    message = records[0].getMessage()
    assert f"budget={budget}" in message
    assert f"size={final_size}" in message
    assert "processes" in message
    for name in _process_names():
        assert name not in message
    assert SENTINEL not in message
    assert str(2**40) not in message


def test_no_degradation_and_no_warning_when_snapshot_fits(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=BUDGET_LOGGER)
    groups = _four_group_fixture()
    exact = _wire_size(groups)

    text = _fit(groups, exact)
    assert text == _envelope(groups)
    assert groups == _four_group_fixture()
    assert _budget_records(caplog) == []


async def test_hello_and_error_messages_are_never_degraded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=BUDGET_LOGGER)
    socket = _CapturingSocket()
    hub = BroadcastHub()
    assert await hub.connect("scope", "test-ip", 4) is None
    sender = _OutboundMessages(
        cast(WebSocket, socket), hub, "scope", timeout=1.0, budget_bytes=1
    )
    try:
        hello_raw = hub.build_hello_message()
        await sender.send(hello_raw)
        error_raw = ServerMessage(
            v=1,
            type=ServerMessageType.ERROR,
            seq=0,
            ts=FIXED_TS_MS,
            data=ErrorData(type="error", code="INVALID_MESSAGE", message="Invalid JSON"),
        ).model_dump_json()
        await sender.send(error_raw)
    finally:
        hub.disconnect("scope", "done")

    assert len(socket.sent) == 2
    assert socket.sent[0] == hello_raw
    assert socket.sent[1] == compact_json({**json.loads(error_raw), "seq": 1})
    # A tiny budget must not constrain non-snapshot messages.
    assert len(socket.sent[0].encode("utf-8")) > 1
    assert len(socket.sent[1].encode("utf-8")) > 1
    assert _budget_records(caplog) == []


async def test_guard_preserves_sequence_and_metadata(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=BUDGET_LOGGER)
    socket = _CapturingSocket()
    hub = BroadcastHub()
    assert await hub.connect("seq", "test-ip", 4) is None
    sender = _OutboundMessages(
        cast(WebSocket, socket), hub, "seq", timeout=1.0, budget_bytes=1000
    )
    try:
        await sender.send(hub.build_hello_message())
        raw = compact_json(
            {
                "v": 1,
                "type": "snapshot",
                "seq": 7,
                "ts": FIXED_TS_MS,
                "data": {
                    "type": "snapshot",
                    "groups": _process_groups(),
                    "meta": {"dropped_since_last": 9},
                },
            }
        )
        for _ in range(6):
            hub.publish(raw)
        queued = hub.get_next_message("seq")
        assert queued is not None
        await sender.send(queued)
        for _ in range(2):
            hub.publish(raw)
        queued = hub.get_next_message("seq")
        assert queued is not None
        await sender.send(queued)
    finally:
        hub.disconnect("seq", "done")

    first = json.loads(socket.sent[1])
    second = json.loads(socket.sent[2])
    assert first["v"] == 1
    assert first["type"] == "snapshot"
    assert first["ts"] == FIXED_TS_MS
    assert first["data"]["type"] == "snapshot"
    assert first["seq"] == 3
    assert first["data"]["meta"] == {"dropped_since_last": 2}
    assert first["data"]["groups"]["processes"] == DEGRADED_STATE
    assert len(socket.sent[1].encode("utf-8")) <= 1000
    assert second["seq"] == 5
    assert second["data"]["meta"] == {"dropped_since_last": 1}
    assert len(_budget_records(caplog)) == 2


def test_impossible_envelope_raises_with_one_safe_warning(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(budget_module, "_last_terminal_warning", None)
    caplog.set_level(logging.WARNING, logger=BUDGET_LOGGER)
    groups = {
        "cpu": {"status": "unavailable", "kind": "unsupported", "reason": "no cpu"},
        "memory": {"status": "unavailable", "kind": "unsupported", "reason": "no memory"},
    }
    original = _clone(groups)
    budget = 1

    final_size = _wire_size(groups)
    with pytest.raises(SnapshotBudgetExceeded) as raised:
        _fit(groups, budget)
    assert raised.value.budget_bytes == budget
    assert raised.value.final_size_bytes == final_size
    assert groups == original
    assert final_size > budget
    records = _budget_records(caplog)
    assert len(records) == 1
    message = records[0].getMessage()
    assert message == f"snapshot budget exceeded: budget={budget} size={final_size}"


def test_two_short_unavailable_reasons_fit_minimum_valid_budget(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=BUDGET_LOGGER)
    groups = {
        "cpu": {"status": "unavailable", "kind": "unsupported", "reason": "no cpu"},
        "memory": {"status": "unavailable", "kind": "unsupported", "reason": "no memory"},
    }
    original = _clone(groups)
    size = _wire_size(groups)

    # Only this short two-group fixture fits; longer valid reasons need not fit.
    with pytest.raises(ValidationError):
        Settings(snapshot_size_budget_bytes=4095)
    assert Settings(snapshot_size_budget_bytes=4096).snapshot_size_budget_bytes == 4096
    assert size <= 4096

    text = _fit(groups, 4096)
    assert len(text.encode("utf-8")) == size
    assert groups == original
    assert _budget_records(caplog) == []
