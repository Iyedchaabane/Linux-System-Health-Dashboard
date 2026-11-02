"""FakeClock for deterministic testing of Sampler timing.

This clock allows tests to control time progression and simulate
timeout behavior for the sampler's collect, consumer, and stop operations.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from monitor.domain.values import MonotonicTimestamp, UtcTimestamp


class FakeClock:
    """A controllable clock for testing Sampler timing behavior.

    Provides:
    - monotonic() -> MonotonicTimestamp
    - utc() -> UtcTimestamp
    - async sleep(delay): registers (deadline, future) and awaits
    - async advance(delta): moves time forward; resolves only waiters whose
      deadline is due, in deadline order, awaiting asyncio.sleep(0) after each;
      skips futures that are done or cancelled.
    """

    def __init__(self, mono_start: float = 0.0, utc_start_timestamp: float = 0.0) -> None:
        """Initialize the fake clock.

        Args:
            mono_start: Starting monotonic seconds.
            utc_start_timestamp: Starting UTC timestamp (Unix epoch seconds).
        """
        self._mono = MonotonicTimestamp(seconds=mono_start)
        utc_dt = datetime.fromtimestamp(utc_start_timestamp, tz=UTC)
        self._utc = UtcTimestamp(moment=utc_dt)
        self._sleepers: list[tuple[float, asyncio.Future[None]]] = []
        self._advance_event = asyncio.Event()

    def monotonic(self) -> MonotonicTimestamp:
        """Return the current monotonic timestamp."""
        return self._mono

    def utc(self) -> UtcTimestamp:
        """Return the current UTC timestamp."""
        return self._utc

    async def sleep(self, delay: float) -> None:
        """Sleep until the current time + delay.

        Registers a (deadline, future) tuple and awaits the future.
        The future is resolved by advance().
        """
        deadline = float(self._mono.seconds) + delay

        if delay <= 0:
            # Non-positive delay returns immediately
            return

        future: asyncio.Future[None] = asyncio.get_event_loop().create_future()
        self._sleepers.append((deadline, future))

        try:
            await future
        except asyncio.CancelledError:
            # Remove from sleepers if cancelled
            self._sleepers = [(d, f) for d, f in self._sleepers if f is not future or not f.done()]
            raise

    async def advance(self, delta: float) -> None:
        """Advance the clock by delta seconds.

        Resolves only waiters whose deadline is <= new time, in deadline order.
        After each resolution, yields via asyncio.sleep(0).
        Skips futures that are already done or cancelled.
        """
        old_seconds = self._mono.seconds
        new_seconds = old_seconds + delta
        self._mono = MonotonicTimestamp(seconds=new_seconds)

        # Also advance UTC proportionally (for test simplicity, same delta)
        utc_seconds = self._utc.moment.timestamp() + delta
        self._utc = UtcTimestamp(moment=datetime.fromtimestamp(utc_seconds, tz=UTC))

        # Sort sleepers by deadline, then process
        self._sleepers.sort(key=lambda x: x[0])

        # Process all waiters with deadline <= new_seconds
        i = 0
        while i < len(self._sleepers):
            deadline, future = self._sleepers[i]

            if deadline > new_seconds:
                # No more waiters to process
                break

            if not future.done() and not future.cancelled():
                future.set_result(None)
                # Yield control to allow any callbacks to run
                await asyncio.sleep(0)

            i += 1

        # Remove processed waiters
        self._sleepers = self._sleepers[i:]
