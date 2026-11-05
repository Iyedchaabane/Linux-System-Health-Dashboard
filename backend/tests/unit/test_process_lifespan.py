"""Lifespan cleanup ordering, partial startup and primary-error preservation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import monitor.presentation.api.app as app_module
from monitor.composition import Container
from monitor.config import Settings
from monitor.domain.entities import SystemSnapshot
from monitor.domain.types import Unavailable, UnavailableKind

from ..fakes.fake_clock import FakeClock


@dataclass
class Lifecycle:
    events: list[str] = field(default_factory=list)
    failures: dict[str, BaseException] = field(default_factory=dict)
    start_entered: asyncio.Event = field(default_factory=asyncio.Event)
    release_start: asyncio.Event = field(default_factory=asyncio.Event)
    block_start: bool = False

    def step(self, name: str) -> None:
        self.events.append(name)
        if name in self.failures:
            raise self.failures[name]


@pytest.fixture
def lifecycle(monkeypatch: pytest.MonkeyPatch):
    state = Lifecycle()

    class Hub:
        def __init__(self, **_kwargs: Any) -> None:
            state.step("hub.init")

        async def close(self) -> None:
            state.step("hub.close")

    class Sampler:
        def __init__(self, **_kwargs: Any) -> None:
            state.step("sampler.init")

        async def start(self) -> None:
            state.start_entered.set()
            state.step("sampler.start")
            if state.block_start:
                await state.release_start.wait()

        async def stop(self) -> None:
            state.step("sampler.stop")

    container = Container(
        settings=Settings(),
        snapshot_provider=lambda: None,
        cleanup_callback=lambda: state.step("adapter.close"),
    )
    monkeypatch.setattr(app_module, "load_settings", lambda: container.settings)
    monkeypatch.setattr(app_module, "build_container", lambda _settings: container)
    monkeypatch.setattr(app_module, "BroadcastHub", Hub)
    monkeypatch.setattr(app_module, "Sampler", Sampler)
    return state, container


STARTUP = ["hub.init", "sampler.init", "sampler.start"]
CLEANUP = ["sampler.stop", "hub.close", "adapter.close"]


async def test_normal_shutdown_closes_sampler_hub_then_adapter_once(lifecycle) -> None:
    state, container = lifecycle
    app = FastAPI()
    async with app_module.lifespan(app):
        assert app.state.container is container
        assert app.state.sampler is container.sampler
        assert app.state.hub is container.hub
        assert state.events == STARTUP
    assert state.events == STARTUP + CLEANUP


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        ("hub.init", ["hub.init", "adapter.close"]),
        ("sampler.init", ["hub.init", "sampler.init", "hub.close", "adapter.close"]),
        ("sampler.start", STARTUP + CLEANUP),
    ],
)
async def test_partial_startup_closes_only_initialized_resources(lifecycle, stage, expected) -> None:
    state, _container = lifecycle
    primary = RuntimeError("startup failed")
    state.failures[stage] = primary
    with pytest.raises(RuntimeError) as raised:
        async with app_module.lifespan(FastAPI()):
            pytest.fail("failed startup must not yield")
    assert raised.value is primary
    assert state.events == expected


async def test_missing_provider_still_closes_hub_and_adapter(lifecycle) -> None:
    state, container = lifecycle
    container.snapshot_provider = None
    with pytest.raises(RuntimeError, match="snapshot_provider is required"):
        async with app_module.lifespan(FastAPI()):
            pytest.fail("missing provider must prevent startup")
    assert state.events == ["hub.init", "hub.close", "adapter.close"]


@pytest.mark.parametrize("stage", CLEANUP)
@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError])
async def test_cleanup_failure_does_not_skip_remaining_resources(
    lifecycle, stage, error_type
) -> None:
    state, _container = lifecycle
    failure = error_type("cleanup failed")
    state.failures[stage] = failure
    with pytest.raises(error_type) as raised:
        async with app_module.lifespan(FastAPI()):
            pass
    assert raised.value is failure
    assert state.events == STARTUP + CLEANUP


async def test_first_cleanup_failure_is_preserved_when_all_cleanup_steps_fail(lifecycle) -> None:
    state, _container = lifecycle
    failures = {stage: RuntimeError(stage) for stage in CLEANUP}
    state.failures.update(failures)
    with pytest.raises(RuntimeError) as raised:
        async with app_module.lifespan(FastAPI()):
            pass
    assert raised.value is failures["sampler.stop"]
    assert state.events == STARTUP + CLEANUP


@pytest.mark.parametrize("during_startup", [True, False])
@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError])
async def test_cleanup_failures_never_mask_primary_startup_or_body_exception(
    lifecycle, during_startup, error_type
) -> None:
    state, _container = lifecycle
    primary = error_type("primary failure")
    state.failures.update({stage: RuntimeError(stage) for stage in CLEANUP})
    if during_startup:
        state.failures["sampler.start"] = primary
    with pytest.raises(error_type) as raised:
        async with app_module.lifespan(FastAPI()):
            raise primary
    assert raised.value is primary
    assert state.events == STARTUP + CLEANUP


async def test_task_cancelled_during_start_still_stops_initialized_sampler(lifecycle) -> None:
    state, _container = lifecycle
    state.block_start = True

    async def run() -> None:
        async with app_module.lifespan(FastAPI()):
            pytest.fail("cancelled startup must not yield")

    task = asyncio.create_task(run())
    try:
        await asyncio.wait_for(state.start_entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
        assert state.events == STARTUP + CLEANUP
    finally:
        state.release_start.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_container_without_optional_cleanup_callback_still_shuts_down(lifecycle) -> None:
    state, container = lifecycle
    container.cleanup_callback = None
    async with app_module.lifespan(FastAPI()):
        pass
    assert state.events == [*STARTUP, "sampler.stop", "hub.close"]


@pytest.mark.integration
async def test_production_lifespan_requests_only_read_sampler_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requests never collect, before or after the real sampler publishes."""
    entered = asyncio.Event()
    release = asyncio.Event()
    cached = asyncio.Event()
    calls = 0
    tasks_before = asyncio.all_tasks()

    class CacheObservedClock(FakeClock):
        async def sleep(self, delay: float) -> None:
            # Observe the next cadence wait, AFTER the real sampler sets latest.
            # Consumer completion alone would race with that cache assignment.
            if container.sampler is not None and container.sampler.latest() is snapshot:
                cached.set()
            await super().sleep(delay)

    clock = CacheObservedClock(utc_start_timestamp=1234.0)
    unavailable = Unavailable(kind=UnavailableKind.UNSUPPORTED, reason="synthetic fixture")
    snapshot = SystemSnapshot(
        cpu=unavailable,
        memory=unavailable,
        disk=unavailable,
        network=unavailable,
        timestamp_monotonic=clock.monotonic(),
        timestamp_utc=clock.utc(),
    )

    async def collect() -> SystemSnapshot:
        nonlocal calls
        calls += 1
        entered.set()
        await release.wait()
        return snapshot

    container = Container(
        settings=Settings(sample_interval_seconds=1.0),
        clock=clock,
        snapshot_provider=collect,
    )
    monkeypatch.setattr(app_module, "load_settings", lambda: container.settings)
    monkeypatch.setattr(app_module, "build_container", lambda _settings: container)
    app = app_module.create_app()

    async with app.router.lifespan_context(app):
        try:
            await asyncio.wait_for(entered.wait(), 1)
            assert calls == 1
            assert container.sampler.latest() is None
            assert await container.snapshot_provider() is None
            # Nonzero collection duration places the next tick in the future.
            # Freeze there so requests cannot coincide with a scheduled sample.
            await clock.advance(0.25)
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                pending_snapshot, pending_ready = await asyncio.wait_for(
                    asyncio.gather(
                        client.get("/api/v1/snapshot"), client.get("/api/v1/readyz")
                    ),
                    1,
                )
                for response, code, message in (
                    (pending_snapshot, "snapshot_not_ready", "No snapshot collected yet"),
                    (pending_ready, "NOT_READY", "No snapshot yet"),
                ):
                    assert response.status_code == 503
                    body = response.json()
                    request_id = body["error"]["request_id"]
                    assert isinstance(request_id, str) and request_id
                    assert body == {
                        "error": {"code": code, "message": message, "request_id": request_id}
                    }
                assert not release.is_set()
                assert container.sampler.latest() is None
                assert calls == 1

                release.set()
                await asyncio.wait_for(cached.wait(), 1)
                assert container.sampler.latest() is snapshot
                assert await container.snapshot_provider() is snapshot
                ready_snapshot, ready = await asyncio.wait_for(
                    asyncio.gather(
                        client.get("/api/v1/snapshot"), client.get("/api/v1/readyz")
                    ),
                    1,
                )
                assert ready_snapshot.status_code == 200
                assert ready_snapshot.json() == {
                    "ts": 1234000,
                    "groups": {
                        group: {
                            "status": "unavailable",
                            "kind": "unsupported",
                            "reason": "synthetic fixture",
                        }
                        for group in ("cpu", "memory", "disk", "network")
                    },
                    "meta": None,
                }
                assert ready.status_code == 200
                assert ready.json() == {"status": "ok"}
                assert container.sampler.latest() is snapshot
                assert calls == 1
        finally:
            release.set()

    assert not (asyncio.all_tasks() - tasks_before)
