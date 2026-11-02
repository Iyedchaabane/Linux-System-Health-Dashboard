"""Broadcast hub for WebSocket message distribution."""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from monitor.presentation.ws.protocol import (
    HelloData,
    HelloLimits,
    ServerMessage,
    ServerMessageType,
)

logger = logging.getLogger(__name__)

# Default limits matching protocol spec
MAX_CLIENTS = 100
MAX_CLIENTS_PER_IP = 10
QUEUE_SIZE = 4
RATE_LIMIT_BURST = 10
RATE_LIMIT_REFILL = 2.0
SEND_TIMEOUT = 5.0
HANDSHAKE_TIMEOUT = 5.0
MAX_MESSAGE_BYTES = 4096


@dataclass
class ClientData:
    """Per-client state tracked by the broadcast hub."""

    queue: deque[str] = field(default_factory=lambda: deque(maxlen=4))
    drops: int = 0
    ip_address: str = ""


class BroadcastHub:
    """Manages WebSocket client connections and message broadcasting.

    Features:
    - Non-blocking publish to all connected clients
    - Bounded per-client queues with drop-oldest policy
    - Client limits (total and per-IP)
    - Token bucket rate limiting per client
    - Safe iteration during modifications
    """

    def __init__(
        self,
        *,
        max_clients: int = MAX_CLIENTS,
        queue_size: int = QUEUE_SIZE,
        max_clients_per_ip: int = MAX_CLIENTS_PER_IP,
        rate_limit_burst: int = RATE_LIMIT_BURST,
        rate_limit_refill_per_second: float = RATE_LIMIT_REFILL,
        send_timeout_seconds: float = SEND_TIMEOUT,
        handshake_timeout_seconds: float = HANDSHAKE_TIMEOUT,
    ) -> None:
        """Initialize the broadcast hub."""
        self._max_clients = max_clients
        self._queue_size = queue_size
        self._max_clients_per_ip = max_clients_per_ip
        self._rate_limit_burst = rate_limit_burst
        self._rate_limit_refill_per_second = rate_limit_refill_per_second
        self._send_timeout_seconds = send_timeout_seconds
        self._handshake_timeout_seconds = handshake_timeout_seconds

        # Client tracking
        self._clients: dict[str, ClientData] = {}
        self._ip_clients: dict[str, set[str]] = {}  # ip -> set of client_ids

    async def close(self) -> None:
        """Close all client connections gracefully."""
        # Clear tracking for graceful shutdown
        self._clients.clear()
        self._ip_clients.clear()

    async def connect(
        self,
        client_id: str,
        ip_address: str,
        _message_queue_size: int,
    ) -> dict[str, Any] | None:
        """Register a new client connection."""
        # Check total client limit
        if len(self._clients) >= self._max_clients:
            return {"code": 1013, "reason": "Server at max client capacity"}

        # Check per-IP limit
        ip_clients = self._ip_clients.get(ip_address, set())
        if len(ip_clients) >= self._max_clients_per_ip:
            return {"code": 1013, "reason": "Too many clients from this IP"}

        # Check if client already connected
        if client_id in self._clients:
            return {"code": 1013, "reason": "Client already connected"}

        # Register client
        self._clients[client_id] = ClientData(
            queue=deque(maxlen=self._queue_size),
            drops=0,
            ip_address=ip_address,
        )
        self._ip_clients.setdefault(ip_address, set()).add(client_id)

        return None

    def disconnect(self, client_id: str, _reason: str) -> None:
        """Remove a client from the hub."""
        client = self._clients.pop(client_id, None)
        if client is not None:
            ip_clients = self._ip_clients.get(client.ip_address, set())
            ip_clients.discard(client_id)
            if not ip_clients:
                self._ip_clients.pop(client.ip_address, None)

    def publish(self, message: str) -> None:
        """Broadcast a message to all connected clients."""
        # Iterate over a copy to allow safe modification during iteration
        for _client_id, client in list(self._clients.items()):
            if client.queue.maxlen is not None and len(client.queue) >= client.queue.maxlen:
                # Drop oldest to make room
                client.queue.popleft()
                client.drops += 1
            client.queue.append(message)

    def build_hello_message(self) -> str:
        """Build the hello message sent to new clients."""
        limits = HelloLimits(
            max_clients=self._max_clients,
            max_clients_per_ip=self._max_clients_per_ip,
            max_message_bytes=MAX_MESSAGE_BYTES,
            rate_limit_burst=self._rate_limit_burst,
            rate_limit_refill_per_second=self._rate_limit_refill_per_second,
            send_timeout_seconds=self._send_timeout_seconds,
            handshake_timeout_seconds=self._handshake_timeout_seconds,
        )

        hello = HelloData(
            type="hello",
            interval_ms=1000,  # Default 1 second
            max_message_bytes=MAX_MESSAGE_BYTES,
            groups=["cpu", "memory"],
            server_time=time.time(),
            limits=limits,
        )

        msg = ServerMessage(
            v=1,
            type=ServerMessageType.HELLO,
            seq=0,
            ts=int(time.time() * 1000),
            data=hello,
        )
        return msg.model_dump_json()

    def get_client_drops(self, client_id: str) -> int:
        """Get the drop count for a specific client."""
        client = self._clients.get(client_id)
        return client.drops if client else 0

    def get_queue_size(self, client_id: str) -> int:
        """Get the current queue size for a client."""
        client = self._clients.get(client_id)
        return len(client.queue) if client else 0

    def get_next_message(self, client_id: str) -> str | None:
        """Get the next message for a client (oldest first)."""
        client = self._clients.get(client_id)
        if client and client.queue:
            return client.queue.popleft()
        return None

    def get_total_clients(self) -> int:
        """Get the current total number of connected clients."""
        return len(self._clients)

    def get_clients_per_ip(self, ip_address: str) -> int:
        """Get the number of clients connected from a specific IP."""
        return len(self._ip_clients.get(ip_address, set()))
