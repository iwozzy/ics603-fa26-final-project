"""Bounded, process-local hydration queue."""
import asyncio
from collections.abc import Callable
from time import monotonic

from lumiere.application.ports.filmography import HydrationEvent, HydrationEventKind
from lumiere.application.use_cases.hydrate_filmography import HydrateFilmography
from lumiere.domain.access import GuestContext
from lumiere.domain.following import PersonIdentity


class FilmographyHydrator:
    def __init__(
        self,
        hydrate: HydrateFilmography,
        *,
        max_pending: int = 1024,
        max_concurrent: int = 10,
        shutdown_timeout: float = 5,
        report: Callable[[HydrationEvent], None] | None = None,
    ) -> None:
        if min(max_pending, max_concurrent, shutdown_timeout) <= 0:
            raise ValueError('hydration queue bounds must be positive')
        self.hydrate = hydrate
        self._max_pending = max_pending
        self._max_concurrent = max_concurrent
        self._shutdown_timeout = shutdown_timeout
        self._report = report
        self._queue: asyncio.Queue[tuple[PersonIdentity, GuestContext]] = asyncio.Queue(max_pending)
        self._identities: set[PersonIdentity] = set()
        self._workers: list[asyncio.Task[None]] = []
        self._closing: asyncio.Task[None] | None = None
        self._accepting = False
        self._in_flight = 0

    @property
    def outstanding(self) -> int:
        return len(self._identities)

    @property
    def in_flight(self) -> int:
        return self._in_flight

    def start(self) -> None:
        if self._workers or self._closing is not None:
            raise RuntimeError('filmography hydrator already started or closed')
        self._workers = [
            asyncio.create_task(self._work(), name='filmography-worker')
            for _ in range(self._max_concurrent)
        ]
        self._accepting = True

    def enqueue(self, identity: PersonIdentity, context: GuestContext) -> bool:
        if not self._accepting:
            self._emit('dropped')
            return False
        if identity in self._identities:
            self._emit('coalesced')
            return False
        if self.outstanding >= self._max_pending:
            self._emit('dropped')
            return False
        self._identities.add(identity)
        self._queue.put_nowait((identity, context))
        self._emit('accepted')
        return True

    async def _work(self) -> None:
        while True:
            identity, context = await self._queue.get()
            self._in_flight += 1
            started = monotonic()
            self._emit('started')
            outcome: HydrationEventKind = 'succeeded'
            try:
                await self.hydrate.execute(identity, context)
            except asyncio.CancelledError:
                outcome = 'dropped'
                raise
            except Exception:  # noqa: BLE001 — one job failure cannot stop the worker
                outcome = 'failed'
            finally:
                self._in_flight -= 1
                self._identities.remove(identity)
                self._queue.task_done()
                self._emit(outcome, duration_ms=int((monotonic() - started) * 1000))

    def _emit(self, kind: HydrationEventKind, *, duration_ms: int = 0) -> None:
        if self._report is not None:
            try:
                self._report(HydrationEvent(kind, self.outstanding, self.in_flight, duration_ms=duration_ms))
            except Exception:  # noqa: BLE001, S110 — queue progress is independent of telemetry
                pass

    async def drain(self) -> None:
        await self._queue.join()

    async def close(self) -> None:
        self._accepting = False
        if self._closing is None:
            self._closing = asyncio.create_task(self._shutdown(), name='filmography-close')
        try:
            await asyncio.shield(self._closing)
        except asyncio.CancelledError:
            await asyncio.shield(self._closing)
            raise

    async def _shutdown(self) -> None:
        try:
            async with asyncio.timeout(self._shutdown_timeout):
                await self.drain()
        except TimeoutError:
            pass
        finally:
            for worker in self._workers:
                worker.cancel()
            await asyncio.gather(*self._workers, return_exceptions=True)
            while not self._queue.empty():
                identity, _ = self._queue.get_nowait()
                self._identities.remove(identity)
                self._queue.task_done()
                self._emit('dropped')
