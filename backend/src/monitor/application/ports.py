"""Application ports for orchestration and history."""

from __future__ import annotations

from typing import Protocol

from monitor.domain.entities import SystemSnapshot
from monitor.domain.values import UtcTimestamp


class Sampler(Protocol):
    """Port for the sampling loop."""

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    def latest(self) -> SystemSnapshot | None: ...


class HistoryStore(Protocol):
    """Port for snapshot persistence and queries."""

    async def append(self, snapshot: SystemSnapshot, occurred_at_utc: UtcTimestamp) -> None: ...

    async def query(self, window_seconds: int, limit: int) -> list[SystemSnapshot]: ...
