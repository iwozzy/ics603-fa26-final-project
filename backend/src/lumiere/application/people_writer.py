"""Bounded, best-effort batches; queue entries remain data until a slot is free."""
import asyncio
from collections import deque
from collections.abc import Callable
from time import monotonic
from typing import Literal

from lumiere.application.ports.people import PeopleUnitOfWorkFactory, PeopleWriteEvent
from lumiere.domain.people import PersonSummary

WriteOutcome = tuple[Literal["succeeded", "failed"], int, int]


class PeopleWriter:
    def __init__(self, uow_factory: PeopleUnitOfWorkFactory, *, max_pending: int = 1024, max_concurrent: int = 10, attempt_timeout: float = 5, max_attempts: int = 3, retry_delay: float = 1, shutdown_timeout: float = 5, report: Callable[[PeopleWriteEvent], None] | None = None) -> None:
        if min(max_pending, max_concurrent, attempt_timeout, max_attempts, shutdown_timeout) <= 0 or retry_delay < 0:
            raise ValueError('people writer bounds must be positive')
        self.uow_factory = uow_factory
        self.max_pending = max_pending
        self.max_concurrent = max_concurrent
        self.attempt_timeout = attempt_timeout
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay
        self.shutdown_timeout = shutdown_timeout
        self.report = report
        self._queue: deque[tuple[PersonSummary, ...]] = deque()
        self._tasks: set[asyncio.Task[WriteOutcome]] = set()
        self._dispatcher: asyncio.Task[None] | None = None
        self._closing: asyncio.Task[None] | None = None
        self._accepting = False
        self._outstanding = 0
        self._wake = asyncio.Event()
        self._idle = asyncio.Event()
        self._idle.set()

    @property
    def outstanding(self) -> int:
        return self._outstanding

    @property
    def in_flight(self) -> int:
        return len(self._tasks)

    def start(self) -> None:
        if self._dispatcher is not None or self._closing is not None:
            raise RuntimeError('people writer already started or closed')
        self._dispatcher = asyncio.create_task(self._dispatch(), name='people-dispatcher')
        self._accepting = True

    def enqueue(self, people: tuple[PersonSummary, ...]) -> bool:
        if not people or not self._accepting or self._dispatcher is None or self._dispatcher.done() or self.outstanding >= self.max_pending:
            self._emit('dropped')
            return False
        self._queue.append(people)
        self._outstanding += 1
        self._idle.clear()
        self._wake.set()
        self._emit('accepted')
        return True

    async def _dispatch(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            while self._queue and self.in_flight < self.max_concurrent:
                task = asyncio.create_task(self._persist(self._queue.popleft()), name='people-batch')
                self._tasks.add(task)
                task.add_done_callback(self._completed)
                self._emit('started')

    def _completed(self, task: asyncio.Task[WriteOutcome]) -> None:
        self._tasks.remove(task)
        self._outstanding -= 1
        # Terminal events reflect released capacity, including shutdown losses.
        if task.cancelled():
            self._emit('dropped')
        elif task.exception() is not None:
            self._emit('failed')
        else:
            kind, attempt, duration_ms = task.result()
            self._emit(kind, attempt, duration_ms)
        if not self.outstanding:
            self._idle.set()
        if self._queue:
            self._wake.set()

    async def _persist(self, people: tuple[PersonSummary, ...]) -> WriteOutcome:
        attempt = 0
        while True:
            attempt += 1
            started = monotonic()
            try:
                async with asyncio.timeout(self.attempt_timeout):
                    async with self.uow_factory() as uow:
                        await uow.people.upsert_batch(people)
                        await uow.commit()
            except Exception:  # noqa: BLE001 — bounded best-effort retry, no exception content
                duration = int((monotonic() - started) * 1000)
                if attempt == self.max_attempts:
                    return ('failed', attempt, duration)
                self._emit('retry', attempt, duration)
                await asyncio.sleep(self.retry_delay)
            else:
                return ('succeeded', attempt, int((monotonic() - started) * 1000))

    def _emit(self, kind: Literal['accepted', 'dropped', 'started', 'succeeded', 'retry', 'failed'], attempt: int = 0, duration_ms: int = 0) -> None:
        if self.report is not None:
            try:
                self.report(PeopleWriteEvent(kind, self.outstanding, self.in_flight, attempt, duration_ms))
            except Exception:  # noqa: BLE001, S110 — observability is best-effort too
                pass

    async def drain(self) -> None:
        await self._idle.wait()

    async def close(self) -> None:
        self._accepting = False
        if self._closing is None:
            self._closing = asyncio.create_task(self._shutdown(), name='people-close')
        try:
            await asyncio.shield(self._closing)
        except asyncio.CancelledError:
            await asyncio.shield(self._closing)
            raise

    async def _shutdown(self) -> None:
        try:
            async with asyncio.timeout(self.shutdown_timeout):
                await self.drain()
        except TimeoutError:
            pass
        finally:
            tasks: list[asyncio.Task[WriteOutcome] | asyncio.Task[None]] = list(self._tasks)
            if self._dispatcher is not None:
                tasks.append(self._dispatcher)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            while self._queue:
                self._queue.popleft()
                self._outstanding -= 1
                self._emit('dropped')
            self._idle.set()
