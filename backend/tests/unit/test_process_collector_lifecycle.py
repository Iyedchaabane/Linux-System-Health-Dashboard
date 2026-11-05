"""Deterministic admission, cancellation and resource ownership regressions."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from concurrent.futures import Future
from threading import Event
from typing import Any

import pytest

import monitor.infrastructure.psutil_process as process_module
from monitor.domain.entities import ProcessList
from monitor.domain.types import MetricResult, Ok, Unavailable, UnavailableKind
from monitor.infrastructure.psutil_process import PsutilProcessReader


class ControlledExecutor:
    """Accept submissions without executing OS calls or scheduling threads."""

    def __init__(self, **kwargs: Any) -> None:
        self.options = kwargs
        self.futures: list[Future[MetricResult[ProcessList]]] = []
        self.submitted = asyncio.Queue[Future[MetricResult[ProcessList]]]()
        self.shutdown_calls: list[dict[str, bool]] = []

    def submit(self, _callable: Any) -> Future[MetricResult[ProcessList]]:
        future: Future[MetricResult[ProcessList]] = Future()
        assert future.set_running_or_notify_cancel()
        self.futures.append(future)
        self.submitted.put_nowait(future)
        return future

    def shutdown(self, **kwargs: bool) -> None:
        self.shutdown_calls.append(kwargs)


@pytest.fixture
def executors(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[ControlledExecutor]]:
    created: list[ControlledExecutor] = []

    def create(**kwargs: Any) -> ControlledExecutor:
        executor = ControlledExecutor(**kwargs)
        created.append(executor)
        return executor

    monkeypatch.setattr(process_module, "ThreadPoolExecutor", create)
    yield created
    for executor in created:
        for future in executor.futures:
            if not future.done():
                future.set_result(Ok(ProcessList(items=(), skipped=0)))


def assert_transient(result: MetricResult[ProcessList]) -> None:
    assert isinstance(result, Unavailable)
    assert result.kind is UnavailableKind.TRANSIENT


async def test_concurrent_reads_submit_once_and_recover_after_completion(executors) -> None:
    reader = PsutilProcessReader()
    first = asyncio.create_task(reader.read())
    # call_soon is an event-loop barrier, not a time-based scheduling guess.
    started = asyncio.Event()
    asyncio.get_running_loop().call_soon(started.set)
    try:
        await asyncio.wait_for(started.wait(), 1)
        assert len(executors) == 1
        executor = executors[0]
        flight = await asyncio.wait_for(executor.submitted.get(), 1)
        for _ in range(10):
            assert_transient(await asyncio.wait_for(reader.read(), 1))
        assert len(executor.futures) == 1
        expected = Ok(ProcessList(items=(), skipped=1), partial=True)
        flight.set_result(expected)
        assert await asyncio.wait_for(first, 1) is expected

        second = asyncio.create_task(reader.read())
        try:
            fresh_flight = await asyncio.wait_for(executor.submitted.get(), 1)
            fresh = Ok(ProcessList(items=(), skipped=0))
            fresh_flight.set_result(fresh)
            assert await asyncio.wait_for(second, 1) is fresh
            assert len(executor.futures) == 2
        finally:
            second.cancel()
            await asyncio.gather(second, return_exceptions=True)
    finally:
        reader.close()
        first.cancel()
        await asyncio.gather(first, return_exceptions=True)


async def test_cancelled_waiter_retains_flight_and_never_replays_abandoned_result(executors) -> None:
    reader = PsutilProcessReader()
    waiter = asyncio.create_task(reader.read())
    started = asyncio.Event()
    asyncio.get_running_loop().call_soon(started.set)
    try:
        await asyncio.wait_for(started.wait(), 1)
        executor = executors[0]
        flight = await asyncio.wait_for(executor.submitted.get(), 1)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert flight.running()
        assert not flight.cancelled()
        for _ in range(10):
            assert_transient(await asyncio.wait_for(reader.read(), 1))
        assert len(executor.futures) == 1

        abandoned = Ok(ProcessList(items=(), skipped=4), partial=True)
        flight.set_result(abandoned)
        next_waiter = asyncio.create_task(reader.read())
        try:
            fresh_flight = await asyncio.wait_for(executor.submitted.get(), 1)
            assert fresh_flight is not flight
            fresh = Ok(ProcessList(items=(), skipped=0))
            fresh_flight.set_result(fresh)
            assert await asyncio.wait_for(next_waiter, 1) is fresh
            assert len(executor.futures) == 2
        finally:
            next_waiter.cancel()
            await asyncio.gather(next_waiter, return_exceptions=True)
    finally:
        reader.close()
        waiter.cancel()
        await asyncio.gather(waiter, return_exceptions=True)


async def test_lazy_private_single_worker_and_idempotent_close(executors) -> None:
    readers = [PsutilProcessReader(), PsutilProcessReader()]
    tasks: list[asyncio.Task] = []
    assert executors == []
    try:
        for reader in readers:
            task = asyncio.create_task(reader.read())
            tasks.append(task)
            started = asyncio.Event()
            asyncio.get_running_loop().call_soon(started.set)
            await asyncio.wait_for(started.wait(), 1)
        assert len(executors) == 2
        for reader, executor in zip(readers, executors, strict=True):
            assert executor.options["max_workers"] == 1
            assert len(executor.futures) == 1
            reader.close()
            reader.close()
            assert executor.shutdown_calls == [{"wait": False, "cancel_futures": True}]
            assert_transient(await reader.read())
            assert len(executor.futures) == 1
    finally:
        for reader in readers:
            reader.close()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_close_before_first_read_never_constructs_executor(executors) -> None:
    reader = PsutilProcessReader()
    reader.close()
    reader.close()
    assert_transient(await reader.read())
    assert executors == []


async def test_real_worker_close_is_nonwaiting_and_cancellation_does_not_stop_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = PsutilProcessReader()
    release = Event()
    finished = Event()
    entered = asyncio.Event()
    loop = asyncio.get_running_loop()
    expected = Ok(ProcessList(items=(), skipped=0))

    def blocked_collection():
        loop.call_soon_threadsafe(entered.set)
        try:
            if not release.wait(3):
                raise AssertionError("test did not release worker")
            return expected
        finally:
            finished.set()

    monkeypatch.setattr(reader, "_read_blocking", blocked_collection)
    waiter = asyncio.create_task(reader.read())
    try:
        await asyncio.wait_for(entered.wait(), 1)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert reader._flight is not None
        assert reader._flight.running()
        assert_transient(await reader.read())
        reader.close()
        reader.close()
        assert not finished.is_set()
        responsive = asyncio.Event()
        loop.call_soon(responsive.set)
        await asyncio.wait_for(responsive.wait(), 1)
        assert_transient(await reader.read())
    finally:
        release.set()
        reader.close()
        waiter.cancel()
        await asyncio.gather(waiter, return_exceptions=True)
        if reader._flight is not None:
            assert await asyncio.wait_for(asyncio.wrap_future(reader._flight), 1) is expected
        assert finished.is_set()
