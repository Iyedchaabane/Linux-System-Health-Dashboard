"""System clock implementation using time.monotonic and datetime.utcnow."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

from monitor.domain.values import MonotonicTimestamp, UtcTimestamp


class SystemClock:
    """System clock using time.monotonic and datetime.now(timezone.utc)."""

    def monotonic(self) -> MonotonicTimestamp:
        return MonotonicTimestamp(seconds=time.monotonic())

    def utc(self) -> UtcTimestamp:
        return UtcTimestamp(moment=datetime.now(UTC))

    async def sleep(self, delay: float) -> None:
        """Sleep for the specified duration using the clock's time source."""
        await asyncio.sleep(delay)
