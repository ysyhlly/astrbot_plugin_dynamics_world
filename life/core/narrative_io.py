"""Bounded worker pool for World operations that use synchronous SQLite."""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from collections.abc import Callable, Hashable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from astrbot.api import logger


class WorldIOBusy(RuntimeError):
    """The worker pool has reached its admission limit."""


class WorldIOClosed(RuntimeError):
    """The worker pool is shutting down."""


@dataclass(eq=False)
class _Job:
    key: Hashable
    call: Callable
    args: tuple
    scope_hash: str
    queued_at: float = field(default_factory=time.perf_counter)
    waiters: set[asyncio.Future] = field(default_factory=set)


class WorldIO:
    """Run bounded synchronous work and share unfinished calls by an exact key."""

    def __init__(
        self, *, max_workers=1, max_pending=8, max_waiters=32,
        thread_name_prefix="world-io",
    ):
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix=thread_name_prefix
        )
        self._max_workers = max_workers
        self._max_pending = max_pending
        self._max_waiters = max_waiters
        self._name = thread_name_prefix
        # Completion may run immediately on the submitter, or on a worker.
        self._lock = threading.RLock()
        self._current = threading.local()
        self._jobs: dict[Hashable, _Job] = {}
        self._pending: deque[_Job] = deque()
        self._running: set[_Job] = set()
        self._waiters = 0
        self._closed = False
        self._start_failed = False
        self._drained: Future = Future()

    async def run(
        self, call: Callable, *args: Any,
        key: Hashable | None = None, scope_hash: str = "",
    ) -> Any:
        waiter = asyncio.get_running_loop().create_future()
        job_key = object() if key is None else key
        with self._lock:
            if self._closed:
                raise WorldIOClosed("World I/O is closed")
            if self._start_failed:
                raise WorldIOBusy("World I/O worker could not start")
            if self._waiters >= self._max_waiters:
                raise WorldIOBusy("World I/O waiter limit reached")
            job = self._jobs.get(job_key)
            if job is None:
                if (
                    len(self._running) >= self._max_workers
                    and len(self._pending) >= self._max_pending
                ):
                    raise WorldIOBusy("World I/O queue is full")
                job = self._jobs[job_key] = _Job(job_key, call, args, scope_hash)
                self._pending.append(job)
            job.waiters.add(waiter)
            self._waiters += 1
            self._dispatch()
        try:
            result = await waiter
            with self._lock:
                if self._closed:
                    raise WorldIOClosed("World I/O is closed")
            return result
        finally:
            with self._lock:
                self._waiters -= 1
                job.waiters.discard(waiter)
                if (
                    not job.waiters
                    and job not in self._running
                    and self._jobs.get(job.key) is job
                ):
                    self._pending.remove(job)
                    self._jobs.pop(job.key)

    def _dispatch(self) -> None:
        while self._pending and len(self._running) < self._max_workers:
            job = self._pending.popleft()
            self._running.add(job)
            try:
                worker = self._executor.submit(self._execute, job)
            except RuntimeError:
                # Executor submission can enqueue work before a thread start fails.
                self._start_failed = True
                self._running.remove(job)
                self._pending.appendleft(job)
                self._fail_pending(WorldIOBusy("World I/O worker could not start"))
                return
            worker.add_done_callback(lambda finished, job=job: self._finish(job, finished))

    def _execute(self, job: _Job) -> Any:
        with self._lock:
            if job not in self._running:
                return None
            if self._closed or not job.waiters:
                self._jobs.pop(job.key)
                return None
        started = time.perf_counter()
        self._current.job = job
        try:
            return job.call(*job.args)
        finally:
            del self._current.job
            queue_ms = (started - job.queued_at) * 1000
            work_ms = (time.perf_counter() - started) * 1000
            log = (
                logger.info
                if queue_ms >= 500 or queue_ms + work_ms >= 1000
                else logger.debug
            )
            log(
                "%s scope_hash=%s queue_ms=%.1f work_ms=%.1f",
                self._name,
                job.scope_hash or "-",
                queue_ms,
                work_ms,
            )

    def seal_current(self) -> None:
        """Keep the current worker's result for callers already waiting for it."""
        job = getattr(self._current, "job", None)
        if job is not None:
            with self._lock:
                if self._jobs.get(job.key) is job:
                    self._jobs.pop(job.key)

    def _finish(self, job: _Job, worker: Future) -> None:
        with self._lock:
            self._running.remove(job)
            if self._jobs.get(job.key) is job:
                self._jobs.pop(job.key)
            if self._closed:
                worker = self._error_result(WorldIOClosed("World I/O is closed"))
            self._deliver(job, worker)
            if self._closed:
                if not self._running:
                    self._drained.set_result(None)
            else:
                self._dispatch()

    @staticmethod
    def _error_result(error: Exception) -> Future:
        result: Future = Future()
        result.set_exception(error)
        return result

    def _fail_pending(self, error: Exception) -> None:
        result = self._error_result(error)
        while self._pending:
            job = self._pending.popleft()
            self._jobs.pop(job.key)
            self._deliver(job, result)

    @staticmethod
    def _set_result(waiter: asyncio.Future, result: Future) -> None:
        if waiter.done():
            return
        if (error := result.exception()) is not None:
            waiter.set_exception(error)
        else:
            waiter.set_result(result.result())

    def _deliver(self, job: _Job, result: Future) -> None:
        for waiter in job.waiters:
            try:
                waiter.get_loop().call_soon_threadsafe(self._set_result, waiter, result)
            except RuntimeError:
                # The caller's event loop may already have exited.
                pass
        job.waiters.clear()

    async def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._closed = True
                self._fail_pending(WorldIOClosed("World I/O is closed"))
                if not self._running:
                    self._drained.set_result(None)
        self._executor.shutdown(wait=False, cancel_futures=True)
        await asyncio.shield(asyncio.wrap_future(self._drained))
        self._executor.shutdown(wait=True)
