"""Background sampler that produces periodic system snapshots."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
from collections.abc import Awaitable, Callable, Coroutine
from enum import Enum
from typing import cast

from monitor.domain.entities import SystemSnapshot
from monitor.domain.ports import Clock
from monitor.domain.values import MonotonicTimestamp

logger = logging.getLogger(__name__)


class _SamplerState(Enum):
    """Internal state of the sampler."""

    STOPPED = "stopped"
    RUNNING = "running"
    STOPPING = "stopping"


class Sampler:
    """Background sampler producing periodic SystemSnapshot instances.

    Uses fixed-rate grid scheduling: collections happen at t=0, interval, 2*interval, ...
    If a collection takes longer than the interval, missed grid slots are skipped and the
    next collection happens at the first slot at or after the previous finish time.
    """

    def __init__(
        self,
        *,
        collect: Callable[[], Awaitable[SystemSnapshot]],
        consumer: Callable[[SystemSnapshot], Awaitable[None]],
        clock: Clock,
        interval: float,
        collect_timeout: float,
        consumer_timeout: float = 1.0,
        stop_timeout: float = 2.0,
    ) -> None:
        """Initialize the sampler.

        Args:
            collect: Callable that produces a SystemSnapshot.
            consumer: Callable that receives each snapshot.
            clock: Clock protocol for time operations.
            interval: Sampling interval in seconds.
            collect_timeout: Timeout for collection operations (real time).
            consumer_timeout: Timeout for consumer operations (real time).
            stop_timeout: Timeout for graceful shutdown (real time).

        Raises:
            ValueError: If interval is not in range [1.0, 10.0].
        """
        if not math.isfinite(interval):
            raise ValueError(f"interval must be finite, got {interval}")
        if interval < 1.0 or interval > 10.0:
            raise ValueError(f"interval must be between 1.0 and 10.0 seconds, got {interval}")

        self._collect = collect
        self._consumer = consumer
        self._clock = clock
        self._interval = interval
        self._collect_timeout = collect_timeout
        self._consumer_timeout = consumer_timeout
        self._stop_timeout = stop_timeout

        self._state = _SamplerState.STOPPED
        self._task: asyncio.Task[None] | None = None
        self._latest: SystemSnapshot | None = None
        self._last_success_at: MonotonicTimestamp | None = None
        self._failures = 0
        self._overruns = 0

        # In-flight tasks for cancellation cleanup
        self._collect_task: asyncio.Task[SystemSnapshot] | None = None
        self._collect_sleep_task: asyncio.Task[None] | None = None
        self._consumer_task: asyncio.Task[None] | None = None
        self._consumer_sleep_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the sampling loop.

        Idempotent: if already running, returns immediately.
        First collection happens at t=0 (immediate).
        """
        # Prevent start during stopping - wait for stop to complete
        task = self._task
        if self._state == _SamplerState.STOPPING and task is not None and not task.done():
            with contextlib.suppress(asyncio.CancelledError):
                await task

        # Idempotent: if already running, return immediately
        if self._state == _SamplerState.RUNNING:
            return

        self._state = _SamplerState.RUNNING
        loop_start = self._clock.monotonic().seconds
        self._task = asyncio.create_task(self._loop(loop_start))
        # Yield multiple times to ensure the background task can run
        # and start collection at t=0
        for _ in range(3):
            await asyncio.sleep(0)

    async def stop(self) -> None:
        """Stop the sampling loop.

        Idempotent: if already stopped, returns immediately.
        Waits for in-flight collection, bounded by stop_timeout.
        CancelledError is always propagated to the caller.
        """
        # Idempotent: if already stopped, return immediately
        if self._state == _SamplerState.STOPPED:
            return

        # Prevent concurrent stop calls
        if self._state == _SamplerState.STOPPING:
            task = self._task
            if task is not None and not task.done():
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            return

        # Transition to STOPPING to prevent new start()
        self._state = _SamplerState.STOPPING

        if self._task is None or self._task.done():
            self._state = _SamplerState.STOPPED
            return

        task = self._task
        try:
            await asyncio.wait_for(task, timeout=self._stop_timeout)
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        finally:
            self._state = _SamplerState.STOPPED

    def latest(self) -> SystemSnapshot | None:
        """Return the most recently published snapshot, or None if none yet."""
        return self._latest

    def last_success_at(self) -> MonotonicTimestamp | None:
        """Return the monotonic timestamp of the last successful collection, or None."""
        return self._last_success_at

    @property
    def failures(self) -> int:
        """Return the number of failed collections or consumer timeouts."""
        return self._failures

    @property
    def overruns(self) -> int:
        """Return the number of collections that exceeded the interval."""
        return self._overruns

    async def _cancel_in_flight_tasks(self) -> None:
        """Cancel and await all in-flight tasks."""
        tasks_to_cancel = [
            self._collect_task,
            self._collect_sleep_task,
            self._consumer_task,
            self._consumer_sleep_task,
        ]
        for task in tasks_to_cancel:
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._collect_task = None
        self._collect_sleep_task = None
        self._consumer_task = None
        self._consumer_sleep_task = None

    async def _loop(self, loop_start: float) -> None:
        """Internal sampling loop with grid scheduling.

        Grid slots are at: loop_start + k * interval for k = 0, 1, 2, ...
        Collections happen at grid slots. If a collection takes longer than the interval,
        the grid skips slots to catch up.
        """
        try:
            # Track current grid slot index
            k = 0

            while self._state == _SamplerState.RUNNING:
                # Calculate next slot time
                next_slot = loop_start + k * self._interval

                # Wait until next slot
                now = self._clock.monotonic().seconds
                if next_slot > now:
                    wait_time = next_slot - now
                    if wait_time > 0:
                        await self._clock.sleep(wait_time)

                # Re-check state after wait
                if self._state != _SamplerState.RUNNING:
                    return

                # Record collection start for overrun calculation
                collection_start = self._clock.monotonic().seconds

                # Perform collection with timeout race using asyncio.wait
                # Pattern from requirements: race collect() against clock.sleep(timeout)
                collect_task: asyncio.Task[SystemSnapshot] = asyncio.create_task(
                    cast("Coroutine[object, object, SystemSnapshot]", self._collect())
                )
                collect_sleep_task: asyncio.Task[None] = asyncio.create_task(
                    cast(
                        "Coroutine[object, object, None]", self._clock.sleep(self._collect_timeout)
                    )
                )
                # Store for cancellation cleanup
                self._collect_task = collect_task
                self._collect_sleep_task = collect_sleep_task
                try:
                    done, pending = await asyncio.wait(
                        {collect_task, collect_sleep_task},
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=self._collect_timeout,
                    )
                finally:
                    # Always clean up the collect race tasks
                    if collect_sleep_task is not None and not collect_sleep_task.done():
                        collect_sleep_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await collect_sleep_task
                    self._collect_sleep_task = None

                # Cancel pending tasks from the wait
                for t in pending:
                    t.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await t

                # Check if it was a timeout (nothing completed)
                if not done:
                    logger.exception("collection timeout")
                    self._failures += 1
                    k += 1
                    self._collect_task = None
                    continue

                # Check if timeout occurred (sleep task in done)
                if collect_sleep_task in done:
                    logger.exception("collection timeout")
                    self._failures += 1
                    k += 1
                    self._collect_task = None
                    continue

                # Get the result from the collect task
                try:
                    snapshot = collect_task.result()
                    if snapshot is None:
                        self._failures += 1
                        k += 1
                        continue
                except Exception as e:
                    logger.exception("collection failed: %s", e)
                    self._failures += 1
                    k += 1
                    continue
                finally:
                    self._collect_task = None

                # Record collection finish time for overrun calculation
                collection_finish = self._clock.monotonic().seconds

                # Perform consumer with timeout race
                consumer_task: asyncio.Task[None] = asyncio.create_task(
                    cast("Coroutine[object, object, None]", self._consumer(snapshot))
                )
                consumer_sleep_task: asyncio.Task[None] = asyncio.create_task(
                    cast(
                        "Coroutine[object, object, None]", self._clock.sleep(self._consumer_timeout)
                    )
                )
                # Store for cancellation cleanup
                self._consumer_task = consumer_task
                self._consumer_sleep_task = consumer_sleep_task
                try:
                    done, pending = await asyncio.wait(
                        {consumer_task, consumer_sleep_task},
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=self._consumer_timeout,
                    )
                finally:
                    # Always clean up the consumer race tasks
                    if consumer_sleep_task is not None and not consumer_sleep_task.done():
                        consumer_sleep_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await consumer_sleep_task
                    self._consumer_sleep_task = None

                for t in pending:
                    t.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await t

                if not done:
                    logger.exception("consumer timeout")
                    self._failures += 1
                    k += 1
                    continue

                if consumer_sleep_task in done:
                    logger.exception("consumer timeout")
                    self._failures += 1
                    k += 1
                    continue

                try:
                    await consumer_task
                except Exception as e:
                    logger.exception("consumer exception: %s", e)
                    self._failures += 1
                    k += 1
                    continue
                finally:
                    self._consumer_task = None

                # Check for overrun
                if collection_finish - collection_start > self._interval:
                    self._overruns += 1

                self._latest = snapshot
                self._last_success_at = self._clock.monotonic()

                # Move to next grid slot.
                # Slots are at loop_start + k * interval; a collection that
                # overruns jumps to the first slot at or after its finish time,
                # skipping missed slots instead of catching up.
                k = math.ceil((collection_finish - loop_start) / self._interval)

        except asyncio.CancelledError:
            # Cancel in-flight tasks before re-raising
            await self._cancel_in_flight_tasks()
            raise
        finally:
            # Only set to STOPPED if not already STOPPING (stop() handles state)
            if self._state == _SamplerState.RUNNING:
                self._state = _SamplerState.STOPPED
