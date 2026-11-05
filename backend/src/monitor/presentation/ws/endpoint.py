"""WebSocket endpoint for the Linux System Health Dashboard."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from typing import Any, cast

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from monitor.config.settings import Settings
from monitor.presentation.ws.budget import (
    DEFAULT_SNAPSHOT_BUDGET_BYTES,
    SnapshotBudgetExceeded,
    compact_json,
    fit_snapshot_to_budget,
)
from monitor.presentation.ws.hub import BroadcastHub
from monitor.presentation.ws.protocol import (
    ErrorData,
    ServerMessage,
    ServerMessageType,
)

logger = logging.getLogger(__name__)

# Constants
MAX_MESSAGE_SIZE = 4096
RATE_LIMIT_BURST = 10
RATE_LIMIT_REFILL = 2.0


class _OutboundMessages:
    """Serialize writes and account for delivery on one connection."""

    def __init__(
        self,
        ws: WebSocket,
        hub: BroadcastHub,
        client_id: str,
        timeout: float,
        budget_bytes: int = DEFAULT_SNAPSHOT_BUDGET_BYTES,
    ) -> None:
        self._ws = ws
        self._hub = hub
        self._client_id = client_id
        self._timeout = timeout
        self._budget_bytes = budget_bytes
        self._lock = asyncio.Lock()
        self._seq = 0
        self._sequenced_drops = 0
        self._delivered_drops = 0

    async def send(self, raw: str) -> None:
        """Assign sequence at the write boundary; acknowledge drops only on success."""
        async with self._lock:
            message = json.loads(raw)
            drops = self._hub.get_client_drops(self._client_id)
            # Hello is always zero, even if snapshots overflow during acceptance.
            if message["type"] != "hello":
                self._seq += drops - self._sequenced_drops
                self._sequenced_drops = drops
            message["seq"] = self._seq
            self._seq += 1
            snapshot = message["type"] == "snapshot"
            if snapshot:
                meta = message["data"].get("meta") or {}
                meta["dropped_since_last"] = drops - self._delivered_drops
                message["data"]["meta"] = meta

                def encode(groups: dict[str, Any]) -> str:
                    message["data"]["groups"] = groups
                    return compact_json(message)

                text = fit_snapshot_to_budget(
                    message["data"]["groups"], encode, self._budget_bytes
                )
            else:
                text = compact_json(message)
            await asyncio.wait_for(self._ws.send_text(text), timeout=self._timeout)
            if snapshot:
                # Drops occurring during the await belong to the next report.
                self._delivered_drops = drops

    async def close(self, code: int, reason: str) -> None:
        """Keep close frames ordered with data writes and bounded by the send timeout."""
        async with self._lock:
            await asyncio.wait_for(self._ws.close(code=code, reason=reason), timeout=self._timeout)


def get_hub_from_ws(ws: WebSocket) -> BroadcastHub:
    """Get the broadcast hub from websocket's app state."""
    hub = ws.app.state.hub
    if hub is None:
        raise RuntimeError("Broadcast hub not configured")
    return cast(BroadcastHub, hub)


def get_settings_from_ws(ws: WebSocket) -> Settings:
    """Get settings from websocket's app state."""
    container = ws.app.state.container
    settings = container.settings
    return cast(Settings, settings)


router = APIRouter()


@router.websocket("/ws/v1/metrics")
async def metrics_ws(
    ws: WebSocket,
) -> None:
    """Handle WebSocket connections for metrics streaming.

    Args:
        ws: The WebSocket connection with injected hub and settings.
    """
    # Get hub and settings from app state
    hub = get_hub_from_ws(ws)
    settings = get_settings_from_ws(ws)

    client_id = f"client-{id(ws)}"
    ip_address = ws.client.host if ws.client else "unknown"

    # Check origin. Browser WebSocket upgrades include Origin; enforce against the
    # allowlist. With an empty allowlist, any origin is rejected while non-browser
    # clients (no Origin header) are still allowed.
    origin = ws.headers.get("origin", "")
    allowed_origins = settings.allowed_origins
    if origin and origin not in allowed_origins:
        logger.warning(f"Blocked origin: {origin}")
        await ws.close(code=1008)
        return

    # Register with hub
    error = await hub.connect(client_id, ip_address, MAX_MESSAGE_SIZE)
    if error is not None:
        logger.warning(f"Client rejected: {error}")
        await ws.close(code=error["code"], reason=error["reason"])
        return

    tasks: list[asyncio.Task[None]] = []
    outbound = _OutboundMessages(
        ws,
        hub,
        client_id,
        settings.ws_send_timeout_seconds,
        settings.snapshot_size_budget_bytes,
    )
    close_code, close_reason = 1000, ""
    try:
        await ws.accept(subprotocol="monitor.v1")
        await outbound.send(hub.build_hello_message())
        tasks.append(
            asyncio.create_task(
                _send_queued_messages(ws, client_id, hub, outbound),
                name=f"ws-sender-{client_id}",
            )
        )
        tasks.append(
            asyncio.create_task(
                _process_client_messages(
                    ws, client_id, float(RATE_LIMIT_BURST), time.monotonic(), settings, outbound
                ),
                name=f"ws-receiver-{client_id}",
            )
        )
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except WebSocketDisconnect:
        logger.debug(f"Client {client_id} disconnected")
    except TimeoutError:
        close_code, close_reason = 1013, "Send timeout"
        logger.warning(f"Send timeout for client {client_id}")
    except SnapshotBudgetExceeded:
        # The shared budget guard already emits the throttled safe diagnostic.
        close_code, close_reason = 1011, "Internal error"
    except Exception as exc:
        close_code, close_reason = 1011, "Internal error"
        logger.exception("Error handling client %s: %s", client_id, exc)
    finally:
        for task in tasks:
            task.cancel()
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            hub.disconnect(client_id, "close")
            if ws.application_state == WebSocketState.CONNECTED:
                with contextlib.suppress(Exception):
                    await outbound.close(close_code, close_reason)


async def _send_queued_messages(
    ws: WebSocket,
    client_id: str,
    hub: BroadcastHub,
    outbound: _OutboundMessages,
) -> None:
    """Let the connection supervisor handle send failures and receiver shutdown."""
    while ws.application_state == WebSocketState.CONNECTED:
        msg = hub.get_next_message(client_id)
        if msg is not None:
            await outbound.send(msg)
            continue
        await asyncio.sleep(0.05)


async def _process_client_messages(
    ws: WebSocket,
    client_id: str,
    initial_tokens: float,
    _last_refill: float,
    settings: Settings,
    outbound: _OutboundMessages,
) -> None:
    """Process messages from the client."""
    rate_tokens = initial_tokens
    lr = _last_refill

    while ws.application_state == WebSocketState.CONNECTED:
        try:
            raw_msg = await asyncio.wait_for(
                ws.receive_text(),
                timeout=settings.ws_handshake_timeout_seconds,
            )
        except TimeoutError:
            logger.debug(f"Timeout waiting for message from {client_id}")
            continue

        # Check message size
        if len(raw_msg) > MAX_MESSAGE_SIZE:
            logger.warning(f"Message too large from {client_id}")
            error_msg = ServerMessage(
                v=1,
                type=ServerMessageType.ERROR,
                seq=0,
                ts=int(time.time() * 1000),
                data=ErrorData(
                    type="error",
                    code="MESSAGE_TOO_LARGE",
                    message="Message exceeds size limit",
                ),
            )
            await outbound.send(error_msg.model_dump_json())
            await outbound.close(code=1009, reason="Message too large")
            return

        # Rate limit check
        now = time.monotonic()
        elapsed = now - lr
        tokens_to_add = elapsed * RATE_LIMIT_REFILL
        rate_tokens = min(float(RATE_LIMIT_BURST), rate_tokens + tokens_to_add)
        lr = now

        if rate_tokens < 1.0:
            logger.warning(f"Rate limit exceeded for {client_id}")
            error_msg = ServerMessage(
                v=1,
                type=ServerMessageType.ERROR,
                seq=0,
                ts=int(time.time() * 1000),
                data=ErrorData(
                    type="error",
                    code="RATE_LIMIT_EXCEEDED",
                    message="Rate limit exceeded",
                ),
            )
            await outbound.send(error_msg.model_dump_json())
            await outbound.close(code=4429, reason="Rate limit exceeded")
            return

        rate_tokens -= 1.0

        # Parse message
        try:
            msg_data = json.loads(raw_msg)
            msg_type = msg_data.get("type")

            # Handle ping - respond with pong
            if msg_type == "ping":
                await outbound.send(
                    json.dumps(
                        {
                            "v": 1,
                            "type": "pong",
                            "seq": 0,
                            "ts": int(time.time() * 1000),
                            "data": {"type": "pong"},
                        }
                    )
                )
            # Handle subscribe - acknowledge for now
            elif msg_type == "subscribe":
                pass

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from {client_id}")
            error_msg = ServerMessage(
                v=1,
                type=ServerMessageType.ERROR,
                seq=0,
                ts=int(time.time() * 1000),
                data=ErrorData(type="error", code="INVALID_MESSAGE", message="Invalid JSON"),
            )
            await outbound.send(error_msg.model_dump_json())
            await outbound.close(code=4400, reason="Invalid message")
            return
