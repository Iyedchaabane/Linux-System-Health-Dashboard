"""Event-driven ASGI transport for deterministic WebSocket tests."""

import asyncio
from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from typing import Any

from starlette.websockets import WebSocket

from monitor.config.settings import Settings
from monitor.presentation.ws.hub import BroadcastHub


class WsTransport:
    def __init__(self, hub: BroadcastHub) -> None:
        self.incoming: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.incoming.put_nowait({"type": "websocket.connect"})
        self.sent: list[dict[str, Any]] = []
        self.on_send: Callable[[dict[str, Any]], Awaitable[None]] | None = None
        self.receiving = asyncio.Event()
        self.socket = WebSocket(
            {
                "type": "websocket",
                "path": "/ws/v1/metrics",
                "headers": [],
                "client": ("127.0.0.1", 1234),
                "app": SimpleNamespace(
                    state=SimpleNamespace(
                        hub=hub, container=SimpleNamespace(settings=Settings(_env_file=None))
                    )
                ),
            },
            self.receive,
            self.send,
        )

    async def receive(self) -> dict[str, Any]:
        self.receiving.set()
        return await self.incoming.get()

    async def send(self, message: dict[str, Any]) -> None:
        if self.on_send is not None:
            await self.on_send(message)
        self.sent.append(message)
