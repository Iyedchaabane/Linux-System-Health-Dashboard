"""Fail-closed regressions with valid budgets, typed payloads and fake time.

The six generic groups exercise the extensible wire model, not six collectors.
The REST failure uses the actual five domain groups, including processes.
"""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
from types import SimpleNamespace
from typing import Any, cast

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.websockets import WebSocket

from monitor.config.settings import Settings
from monitor.domain.types import Unavailable, UnavailableKind
from monitor.presentation.api.app import create_app
from monitor.presentation.api.deps import get_snapshot_provider
from monitor.presentation.api.routes import metrics
from monitor.presentation.api.schemas import SnapshotResponse
from monitor.presentation.ws import budget as budget_module
from monitor.presentation.ws.budget import (
    SnapshotBudgetExceeded,
    compact_json,
    enforce_snapshot_budget,
    fit_snapshot_to_budget,
)
from monitor.presentation.ws.endpoint import _OutboundMessages, metrics_ws
from monitor.presentation.ws.hub import BroadcastHub
from monitor.presentation.ws.protocol import GroupStateUnavailable, ServerMessage
from tests.contract.test_process_payload_budget import _FixedSnapshotProvider, _snapshot
from tests.fakes.ws_transport import WsTransport
from tests.unit.test_snapshot_budget_guard import (
    BUDGET_LOGGER,
    FIXED_TS_MS,
    _CapturingSocket,
    _envelope,
)


@pytest.fixture(autouse=True)
def terminal_clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Patch only this module's time reference, never asyncio's global clock."""
    clock = [0.0]

    def wall_clock_forbidden() -> float:
        raise AssertionError("Terminal throttle must not use wall time")

    monkeypatch.setattr(budget_module, "_last_terminal_warning", None)
    monkeypatch.setattr(
        budget_module,
        "time",
        SimpleNamespace(monotonic=lambda: clock[0], time=wall_clock_forbidden),
    )
    return clock


def _unavailable_groups(names: tuple[str, ...]) -> dict[str, Any]:
    state = GroupStateUnavailable(
        status="unavailable", kind=UnavailableKind.TRANSIENT, reason="\x01" * 512
    )
    return {name: state.model_dump(mode="json") for name in names}


FIVE_GROUPS = ("cpu", "memory", "disk", "network", "processes")
SIX_GENERIC_GROUPS = (*FIVE_GROUPS, "other")


@pytest.mark.parametrize(
    ("names", "budget", "size"),
    [(FIVE_GROUPS, 4096, 15806), (SIX_GENERIC_GROUPS, 16384, 18942)],
)
async def test_valid_budget_rejects_typed_unavailable_envelope_without_send(
    names: tuple[str, ...],
    budget: int,
    size: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=BUDGET_LOGGER)
    settings = Settings(snapshot_size_budget_bytes=budget)
    groups = _unavailable_groups(names)
    original = compact_json(groups)
    raw = ServerMessage.model_validate_json(_envelope(groups)).model_dump_json()
    assert len(raw.encode("utf-8")) == size
    with pytest.raises(SnapshotBudgetExceeded) as error:
        fit_snapshot_to_budget(groups, _envelope, settings.snapshot_size_budget_bytes)
    assert (error.value.budget_bytes, error.value.final_size_bytes) == (budget, size)
    assert compact_json(groups) == original
    socket = _CapturingSocket()
    hub = BroadcastHub()
    assert await hub.connect("terminal", "test-ip", 4) is None
    sender = _OutboundMessages(cast(WebSocket, socket), hub, "terminal", 1.0, budget)
    try:
        await sender.send(hub.build_hello_message())
        with pytest.raises(SnapshotBudgetExceeded) as sent_error:
            await sender.send(raw)
        assert sent_error.value.final_size_bytes == size
        assert [json.loads(text)["type"] for text in socket.sent] == ["hello"]
        assert sender._delivered_drops == 0
    finally:
        hub.disconnect("terminal", "done")
    assert [r.getMessage() for r in caplog.records if r.name == BUDGET_LOGGER] == [
        f"snapshot budget exceeded: budget={budget} size={size}"
    ]
    print(f"SIZE rejected typed WS budget={budget}: final={size}")


def test_terminal_exact_fit_and_one_byte_over_preserve_unavailable() -> None:
    groups = _unavailable_groups(FIVE_GROUPS)
    raw = _envelope(groups)
    exact = len(raw.encode("utf-8"))
    assert Settings(snapshot_size_budget_bytes=exact - 1)
    assert fit_snapshot_to_budget(groups, _envelope, exact) == raw
    with pytest.raises(SnapshotBudgetExceeded) as error:
        fit_snapshot_to_budget(groups, _envelope, exact - 1)
    assert (error.value.budget_bytes, error.value.final_size_bytes) == (exact - 1, exact)
    assert _envelope(groups) == raw


def test_terminal_after_all_candidates_degraded_preserves_original_unavailable(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=BUDGET_LOGGER)
    groups = _unavailable_groups(FIVE_GROUPS)
    original = compact_json(groups)
    groups["private-group-sentinel"] = {
        "status": "ok",
        "value": {"private-value-sentinel": "x" * 5000},
        "partial": False,
    }
    with pytest.raises(SnapshotBudgetExceeded) as error:
        fit_snapshot_to_budget(groups, _envelope, 4096)
    assert groups.pop("private-group-sentinel") == {
        "status": "unavailable",
        "kind": "transient",
        "reason": budget_module.DEGRADED_REASON,
    }
    assert compact_json(groups) == original
    records = [r for r in caplog.records if r.name == BUDGET_LOGGER]
    assert [r.getMessage() for r in records] == [
        f"snapshot budget exceeded: budget=4096 size={error.value.final_size_bytes}"
    ]
    assert records[0].exc_info is None


@pytest.mark.parametrize("pending_drops", [0, 10])
async def test_final_sequence_and_pending_drop_digits_are_measured_before_send(
    pending_drops: int,
) -> None:
    groups = _unavailable_groups(FIVE_GROUPS)
    raw = _envelope(groups)
    budget = len(raw.encode("utf-8"))
    hub = BroadcastHub()
    assert await hub.connect("digits", "test-ip", 4) is None
    socket = _CapturingSocket()
    sender = _OutboundMessages(cast(WebSocket, socket), hub, "digits", 1.0, budget)
    try:
        # Advance using real successful sends, not by rewriting sender internals.
        for _ in range(9):
            await sender.send(hub.build_hello_message())
        await sender.send(raw)
        accepted = json.loads(socket.sent[-1])
        assert accepted["seq"] == 9
        assert accepted["data"]["meta"] == {"dropped_since_last": 0}
        assert len(socket.sent[-1].encode("utf-8")) == budget
        if pending_drops:
            for _ in range(4 + pending_drops):
                hub.publish(raw)
        assert hub.get_client_drops("digits") == pending_drops
        with pytest.raises(SnapshotBudgetExceeded) as error:
            await sender.send(raw)
        final = json.loads(raw)
        final["seq"] = 10 + pending_drops
        final["data"]["meta"]["dropped_since_last"] = pending_drops
        final_size = len(compact_json(final).encode("utf-8"))
        assert final_size == budget + 1 + bool(pending_drops)
        assert error.value.final_size_bytes == final_size
        assert len(socket.sent) == 10
        assert sender._delivered_drops == 0
        assert hub.get_client_drops("digits") == pending_drops
    finally:
        hub.disconnect("digits", "done")


async def test_real_endpoint_supervisor_closes_1011_and_awaits_all_tasks(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)
    hub = BroadcastHub()
    transport = WsTransport(hub)
    transport.socket.app.state.container.settings = Settings(snapshot_size_budget_bytes=4096)
    raw = _envelope(_unavailable_groups(FIVE_GROUPS))
    before = asyncio.all_tasks()

    async def publish_after_hello(message: dict[str, Any]) -> None:
        if message["type"] == "websocket.send":
            assert json.loads(message["text"])["type"] == "hello"
            for _ in range(14):
                hub.publish(raw)

    transport.on_send = publish_after_hello
    await asyncio.wait_for(metrics_ws(transport.socket), timeout=1.0)
    frames = [m for m in transport.sent if m["type"] == "websocket.send"]
    assert [json.loads(m["text"])["type"] for m in frames] == ["hello"]
    assert transport.sent[-1] == {
        "type": "websocket.close",
        "code": 1011,
        "reason": "Internal error",
    }
    assert hub.get_total_clients() == hub.get_clients_per_ip("127.0.0.1") == 0
    assert asyncio.all_tasks() == before
    assert len([r for r in caplog.records if r.name == BUDGET_LOGGER]) == 1
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def _rest_app(snapshot: Any, budget: int = 4096) -> Any:
    app = create_app()
    app.dependency_overrides[get_snapshot_provider] = lambda: _FixedSnapshotProvider(snapshot)
    app.state.container = SimpleNamespace(settings=Settings(snapshot_size_budget_bytes=budget))

    @app.middleware("http")
    async def correlation(request: Any, call_next: Any) -> Any:
        request.state.request_id = "budget-test-request"
        return await call_next(request)

    return app


def _unavailable_snapshot() -> Any:
    unavailable = Unavailable(UnavailableKind.TRANSIENT, "\x01" * 512)
    return replace(_snapshot(1), **dict.fromkeys(FIVE_GROUPS, unavailable))


async def test_actual_rest_terminal_503_and_ws_share_process_wide_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=BUDGET_LOGGER)
    app = _rest_app(_unavailable_snapshot())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/snapshot")
    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "Internal server error",
            "request_id": "budget-test-request",
        }
    }
    # A separate connection/transport in the same process shares the throttle.
    socket = _CapturingSocket()
    hub = BroadcastHub()
    sender = _OutboundMessages(cast(WebSocket, socket), hub, "rest-ws", 1.0, 4096)
    with pytest.raises(SnapshotBudgetExceeded):
        await sender.send(_envelope(_unavailable_groups(FIVE_GROUPS)))
    assert socket.sent == []
    records = [r for r in caplog.records if r.name == BUDGET_LOGGER]
    assert [r.getMessage() for r in records] == ["snapshot budget exceeded: budget=4096 size=15806"]
    print("SIZE rejected actual REST canonical WS budget=4096: final=15806 status=503")


async def test_unrelated_rest_exception_remains_canonical_500() -> None:
    app = _rest_app(_snapshot(1))

    async def broken_provider() -> Any:
        raise RuntimeError("private-path-and-payload-sentinel")

    app.dependency_overrides[get_snapshot_provider] = lambda: broken_provider
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/snapshot")
    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "Internal server error",
            "request_id": "budget-test-request",
        }
    }


@pytest.mark.parametrize("budget", [4096, 16384])
async def test_actual_successful_rest_body_fits_valid_budget(budget: int) -> None:
    app = _rest_app(_snapshot(1), budget)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/snapshot")
    assert response.status_code == 200
    parsed = SnapshotResponse.model_validate_json(response.content)
    assert parsed.ts == FIXED_TS_MS
    assert len(response.content) <= budget
    print(f"SIZE accepted actual REST budget={budget}: final={len(response.content)}")


async def test_rest_final_model_normalization_is_independently_bounded(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Sparse mapper fake isolates normalization, not current collector behavior."""
    caplog.set_level(logging.WARNING, logger=BUDGET_LOGGER)
    groups: dict[str, Any] = {name: {"status": "ok"} for name in FIVE_GROUPS[:4]}
    groups["cpu"]["value"] = {"padding": ""}
    groups["cpu"]["value"]["padding"] = "x" * (4096 - len(_envelope(groups).encode("utf-8")))
    assert len(_envelope(groups).encode("utf-8")) == 4096
    normalized = SnapshotResponse(ts=FIXED_TS_MS, groups=groups, meta=None)
    final_size = max(
        len(normalized.model_dump_json().encode("utf-8")),
        len(compact_json(normalized.model_dump(mode="json")).encode("utf-8")),
    )
    assert final_size > 4096
    for name, group in groups.items():
        monkeypatch.setattr(
            metrics,
            f"_map_{name}_result",
            lambda _result, group=group: SimpleNamespace(model_dump=lambda **_kw: group),
        )
    app = _rest_app(_snapshot(1))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/snapshot")
    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "INTERNAL_ERROR",
        "message": "Internal server error",
        "request_id": "budget-test-request",
    }
    assert [r.getMessage() for r in caplog.records if r.name == BUDGET_LOGGER] == [
        f"snapshot budget exceeded: budget=4096 size={final_size}"
    ]
    print(f"SIZE rejected sparse-mapper REST normalization: canonical=4096 final={final_size}")


def test_terminal_warning_first_at_zero_then_60_seconds_not_59_999(
    terminal_clock: list[float],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=BUDGET_LOGGER)
    for now, count in [(0.0, 1), (0.0, 1), (59.999, 1), (60.0, 2)]:
        terminal_clock[0] = now
        with pytest.raises(SnapshotBudgetExceeded) as error:
            enforce_snapshot_budget(15806, 4096)
        assert vars(error.value) == {"budget_bytes": 4096, "final_size_bytes": 15806}
        records = [r for r in caplog.records if r.name == BUDGET_LOGGER]
        assert len(records) == count
        assert all(
            r.getMessage() == "snapshot budget exceeded: budget=4096 size=15806" for r in records
        )
        assert all(r.exc_info is None for r in records)


def test_concurrent_terminal_warnings_are_process_wide_and_payload_free(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=BUDGET_LOGGER)
    barrier = Barrier(8, timeout=2.0)
    groups = _unavailable_groups((*FIVE_GROUPS, "private-group-sentinel"))
    groups["private-group-sentinel"]["reason"] = "private-reason-sentinel" + "\x01" * 480

    def reject(_: int) -> tuple[int, int]:
        barrier.wait()
        with pytest.raises(SnapshotBudgetExceeded) as error:
            fit_snapshot_to_budget(groups.copy(), _envelope, 4096)
        return error.value.budget_bytes, error.value.final_size_bytes

    with ThreadPoolExecutor(max_workers=8) as pool:
        errors = list(pool.map(reject, range(8)))
    final_size = len(_envelope(groups).encode("utf-8"))
    assert errors == [(4096, final_size)] * 8
    records = [r for r in caplog.records if r.name == BUDGET_LOGGER]
    assert len(records) == 1
    assert records[0].getMessage() == f"snapshot budget exceeded: budget=4096 size={final_size}"
    assert records[0].args == (4096, final_size)
    assert records[0].exc_info is None
