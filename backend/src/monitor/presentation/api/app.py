"""FastAPI application factory for the Linux System Health Dashboard."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI

from monitor.application.sampler import Sampler
from monitor.composition import build_container
from monitor.config import load_settings
from monitor.config.settings import Settings
from monitor.domain.entities import SystemSnapshot
from monitor.domain.ports import Clock
from monitor.presentation.api.errors import register_error_handlers
from monitor.presentation.api.routes.health import router as health_router
from monitor.presentation.api.routes.metrics import router as metrics_router
from monitor.presentation.ws.endpoint import router as ws_router
from monitor.presentation.ws.hub import BroadcastHub
from monitor.presentation.ws.snapshot import serialize_snapshot

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifespan concerns."""
    container = build_container(load_settings())
    initialized_hub: BroadcastHub | None = None
    initialized_sampler: Sampler | None = None
    primary_error: BaseException | None = None
    try:
        app.state.container = container

        settings: Settings = container.settings
        clock: Clock = cast(Clock, container.clock)

        # Hub created and bound during startup
        hub = BroadcastHub(
            max_clients=settings.max_ws_clients,
            queue_size=settings.ws_queue_size,
            max_clients_per_ip=settings.max_ws_clients_per_ip,
            send_timeout_seconds=settings.ws_send_timeout_seconds,
            handshake_timeout_seconds=settings.ws_handshake_timeout_seconds,
        )
        initialized_hub = hub
        app.state.hub = hub
        container.hub = hub

        # Wire Sampler with the existing single CollectSnapshot
        collect_snapshot_provider = container.snapshot_provider
        if collect_snapshot_provider is None:
            raise RuntimeError("snapshot_provider is required")  # noqa: TRY301 - startup guard
        collect_callable = cast(Callable[[], Awaitable[Any]], collect_snapshot_provider)

        async def consumer(snapshot: SystemSnapshot) -> None:
            """Serialize a snapshot and publish it through the hub."""
            try:
                payload = serialize_snapshot(snapshot)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("failed to serialize snapshot: %s", exc)
                return
            try:
                hub.publish(payload)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("failed to publish snapshot: %s", exc)

        async def snapshot_provider() -> SystemSnapshot | None:
            # REST serves the sampler's latest snapshot (no per-request collection).
            return sampler.latest()

        async def collect() -> SystemSnapshot:
            """Apply the existing collect_snapshot use case."""
            result = await collect_callable()
            return cast(SystemSnapshot, result)

        sample_interval = settings.sample_interval_seconds
        collect_timeout = sample_interval * settings.collection_timeout_multiplier

        sampler = Sampler(
            collect=collect,
            consumer=consumer,
            clock=clock,
            interval=sample_interval,
            collect_timeout=collect_timeout,
        )
        initialized_sampler = sampler
        await sampler.start()
        container.sampler = sampler
        container.snapshot_provider = snapshot_provider
        app.state.sampler = sampler

        yield
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        # Attempt every cleanup even after partial startup or cancellation.
        cleanup_error: BaseException | None = None
        try:
            if initialized_sampler is not None:
                await initialized_sampler.stop()
        except BaseException as exc:
            cleanup_error = exc
            logger.exception("sampler shutdown failed")
        try:
            if initialized_hub is not None:
                await initialized_hub.close()
        except BaseException as exc:
            if cleanup_error is None:
                cleanup_error = exc
            logger.exception("hub shutdown failed")
        try:
            if container.cleanup_callback is not None:
                container.cleanup_callback()
        except BaseException as exc:
            if cleanup_error is None:
                cleanup_error = exc
            logger.exception("adapter cleanup failed")
        if primary_error is None and cleanup_error is not None:
            raise cleanup_error


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(title="Linux System Health Dashboard", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(ws_router)
    register_error_handlers(app)
    return app
