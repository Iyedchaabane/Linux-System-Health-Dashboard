"""WebSocket endpoint for the Linux System Health Dashboard."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from typing import cast

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from monitor.config.settings import Settings
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

    # Accept the connection with subprotocol
    await ws.accept(subprotocol="monitor.v1")

    # Build and send hello message
    hello_msg = hub.build_hello_message()
    try:
        await asyncio.wait_for(
            ws.send_text(hello_msg),
            timeout=settings.ws_send_timeout_seconds,
        )
    except TimeoutError:
        logger.warning(f"Timeout sending hello to {client_id}")
        await ws.close(code=1013, reason="Send timeout")
        return

    # Initialize rate limiter
    rate_tokens = float(RATE_LIMIT_BURST)
    last_refill = time.monotonic()

    # Spawn sender task to deliver queued snapshots to this client
    sender_task = asyncio.create_task(
        _send_queued_messages(ws, client_id, hub, settings),
        name=f"ws-sender-{client_id}",
    )

    try:
        # Process messages from client (receiver)
        await _process_client_messages(ws, client_id, rate_tokens, last_refill, settings)
    except WebSocketDisconnect:
        logger.debug(f"Client {client_id} disconnected")
    except Exception as e:
        logger.exception(f"Error handling client {client_id}: {e}")
    finally:
        # Cancel and await sender; ignore cancellation
        sender_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sender_task
        # Clean up
        hub.disconnect(client_id, "close")


async def _send_queued_messages(
    ws: WebSocket,
    client_id: str,
    hub: BroadcastHub,
    settings: Settings,
) -> None:
    """Poll and send queued snapshot messages to the client."""
    while ws.application_state == WebSocketState.CONNECTED:
        try:
            msg = hub.get_next_message(client_id)
            if msg is not None:
                try:
                    await asyncio.wait_for(
                        ws.send_text(msg),
                        timeout=settings.ws_send_timeout_seconds,
                    )
                except TimeoutError:
                    logger.warning(f"Send timeout for client {client_id}")
                    with contextlib.suppress(Exception):
                        await ws.close(code=1013, reason="Send timeout")
                    return
                continue
        except Exception as e:
            logger.exception(f"Sender error for client {client_id}: {e}")
            return
        # Brief poll interval to avoid tight CPU loop
        await asyncio.sleep(0.05)


async def _process_client_messages(
    ws: WebSocket,
    client_id: str,
    initial_tokens: float,
    _last_refill: float,
    settings: Settings,
) -> None:
    """Process messages from the client."""
    seq = 0
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
                seq=seq,
                ts=int(time.time() * 1000),
                data=ErrorData(
                    type="error",
                    code="MESSAGE_TOO_LARGE",
                    message="Message exceeds size limit",
                ),
            )
            await ws.send_text(error_msg.model_dump_json())
            await ws.close(code=1009, reason="Message too large")
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
                seq=seq,
                ts=int(time.time() * 1000),
                data=ErrorData(
                    type="error",
                    code="RATE_LIMIT_EXCEEDED",
                    message="Rate limit exceeded",
                ),
            )
            await ws.send_text(error_msg.model_dump_json())
            await ws.close(code=4429, reason="Rate limit exceeded")
            return

        rate_tokens -= 1.0
        seq += 1

        # Parse message
        try:
            msg_data = json.loads(raw_msg)
            msg_type = msg_data.get("type")

            # Handle ping - respond with pong
            if msg_type == "ping":
                await ws.send_text(
                    json.dumps(
                        {
                            "v": 1,
                            "type": "pong",
                            "seq": seq,
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
                seq=seq,
                ts=int(time.time() * 1000),
                data=ErrorData(type="error", code="INVALID_MESSAGE", message="Invalid JSON"),
            )
            await ws.send_text(error_msg.model_dump_json())
            await ws.close(code=4400, reason="Invalid message")
            return
