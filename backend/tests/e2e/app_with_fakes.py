"""FastAPI test app with fake metrics (deterministic) for E2E."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from monitor.application.collect_snapshot import CollectSnapshot
from monitor.application.sampler import Sampler
from monitor.config import load_settings
from monitor.domain.entities import SystemSnapshot
from monitor.infrastructure.system_clock import SystemClock
from monitor.presentation.api.errors import register_error_handlers
from monitor.presentation.api.routes.health import router as health_router
from monitor.presentation.api.routes.metrics import router as metrics_router
from monitor.presentation.ws.endpoint import router as ws_router
from monitor.presentation.ws.hub import BroadcastHub
from tests.e2e.fakes import FakeCpuReader, FakeDiskReader, FakeMemoryReader, FakeNetworkReader

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = load_settings()
    settings.allowed_origins = ["http://127.0.0.1:3000"]
    clock = SystemClock()
    cpu = FakeCpuReader()
    memory = FakeMemoryReader()
    disk = FakeDiskReader()
    network = FakeNetworkReader()

    collect_snapshot = CollectSnapshot(
        cpu_reader=cpu,
        memory_reader=memory,
        clock=clock,
        disk_reader=disk,
        network_reader=network,
    )

    hub = BroadcastHub(
        max_clients=settings.max_ws_clients,
        queue_size=settings.ws_queue_size,
        max_clients_per_ip=settings.max_ws_clients_per_ip,
        send_timeout_seconds=settings.ws_send_timeout_seconds,
        handshake_timeout_seconds=settings.ws_handshake_timeout_seconds,
    )

    seq_counter = {"value": 0}

    async def consumer(snapshot: SystemSnapshot) -> None:
        from monitor.presentation.ws.snapshot import serialize_snapshot

        seq_counter["value"] += 1
        with suppress(Exception):
            hub.publish(serialize_snapshot(snapshot, seq=seq_counter["value"]))

    async def collect() -> SystemSnapshot:
        return await collect_snapshot()

    interval = settings.sample_interval_seconds
    sampler = Sampler(
        collect=collect,
        consumer=consumer,
        clock=clock,
        interval=interval,
        collect_timeout=interval * settings.collection_timeout_multiplier,
    )
    await sampler.start()

    from monitor.composition import Container

    container = Container(
        settings=settings,
        sampler=sampler,
        hub=hub,
        cpu_reader=cpu,
        memory_reader=memory,
        disk_reader=disk,
        network_reader=network,
        clock=clock,
        snapshot_provider=collect_snapshot,
    )
    app.state.container = container
    app.state.hub = hub
    app.state.sampler = sampler

    try:
        yield
    finally:
        await sampler.stop()
        await hub.close()


def app_factory() -> FastAPI:
    app = FastAPI(title="Linux System Health Dashboard (E2E)", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(ws_router)
    register_error_handlers(app)
    return app


app = app_factory()
