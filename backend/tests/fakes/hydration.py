import asyncio
from collections import deque
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self

from lumiere.application.filmography_hydrator import FilmographyHydrator
from lumiere.application.ports.filmography import FilmographyRepository
from lumiere.application.ports.usage import UsageAdmission
from lumiere.application.provider_dispatch import ProviderDispatch
from lumiere.application.use_cases.hydrate_filmography import HydrateFilmography
from lumiere.domain.access import GuestContext
from lumiere.domain.errors import SearchFailed
from lumiere.domain.filmography import FilmographyPerson, PersonFilmography
from lumiere.domain.following import PersonIdentity


class ControlledHydrationClock:
    def __init__(self, now: datetime = datetime(2026, 11, 26, tzinfo=UTC)) -> None:
        self._now = now
        self._monotonic = 0.0
        self._sleepers: dict[asyncio.Future[None], float] = {}

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._monotonic

    async def sleep(self, seconds: float) -> None:
        sleeper: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._sleepers[sleeper] = self._monotonic + seconds
        try:
            await sleeper
        finally:
            del self._sleepers[sleeper]

    async def advance(self, seconds: float) -> None:
        self._monotonic += seconds
        self.jump_wall(timedelta(seconds=seconds))
        for sleeper, deadline in self._sleepers.items():
            if deadline <= self._monotonic and not sleeper.done():
                sleeper.set_result(None)
        await asyncio.sleep(0)

    def jump_wall(self, delta: timedelta) -> None:
        self._now += delta


class RecordingAdmission:
    def __init__(self) -> None:
        self.charged_contexts: list[GuestContext] = []
        self.reject = False

    async def admit_and_charge(self, context: GuestContext, now: datetime) -> None:
        if self.reject:
            raise SearchFailed("quota")
        self.charged_contexts.append(context)


class RecordingFilmographyQueue:
    def __init__(self) -> None:
        self.enqueued: list[tuple[PersonIdentity, GuestContext]] = []
        self.error: Exception | None = None

    def enqueue(self, identity: PersonIdentity, context: GuestContext) -> bool:
        if self.error:
            raise self.error
        self.enqueued.append((identity, context))
        return True


class ControlledFilmography:
    def __init__(self, clock: ControlledHydrationClock) -> None:
        self.clock = clock
        self.timestamps: dict[PersonIdentity, datetime | None] = {}
        self.stored: dict[PersonIdentity, PersonFilmography] = {}
        self.transactions: list[FilmographyTransaction] = []
        self.active: set[FilmographyTransaction] = set()
        self.reads: list[PersonIdentity] = []
        self.writes: list[PersonFilmography] = []
        self.fail_commits = 0
        self.rollbacks = 0
        self.reading = asyncio.Event()
        self.committing = asyncio.Event()
        self.allow_read = asyncio.Event()
        self.allow_commit = asyncio.Event()
        self.allow_read.set()
        self.allow_commit.set()

    def __call__(self) -> 'FilmographyTransaction':
        uow = FilmographyTransaction(self)
        self.transactions.append(uow)
        return uow


class FilmographyTransaction:
    def __init__(self, store: ControlledFilmography) -> None:
        self.store = store
        self.filmographies: FilmographyRepository = self
        self._pending: PersonFilmography | None = None

    async def __aenter__(self) -> Self:
        self.store.active.add(self)
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None,
                        exc: BaseException | None, tb: TracebackType | None) -> None:
        await self.rollback()
        self.store.active.remove(self)

    async def last_hydrated(self, identity: PersonIdentity) -> datetime | None:
        self.store.reads.append(identity)
        self.store.reading.set()
        await self.store.allow_read.wait()
        return self.store.timestamps.get(identity)

    async def upsert(self, payload: PersonFilmography) -> None:
        self.store.writes.append(payload)
        self._pending = payload

    async def commit(self) -> None:
        assert self._pending is not None
        self.store.committing.set()
        await self.store.allow_commit.wait()
        if self.store.fail_commits:
            self.store.fail_commits -= 1
            raise RuntimeError('synthetic commit failure')
        identity = self._pending.person.identity
        self.store.stored[identity] = self._pending
        self.store.timestamps[identity] = self.store.clock.now()
        self._pending = None

    async def rollback(self) -> None:
        if self._pending is not None:
            self._pending = None
            self.store.rollbacks += 1


class ControlledFilmographyCatalog:
    def __init__(self) -> None:
        self.calls: list[PersonIdentity] = []
        self.errors: deque[Exception] = deque()
        self.fetching = asyncio.Event()
        self.allow_fetch = asyncio.Event()
        self.allow_fetch.set()

    async def fetch(self, identity: PersonIdentity) -> PersonFilmography:
        self.calls.append(identity)
        self.fetching.set()
        await self.allow_fetch.wait()
        if self.errors:
            raise self.errors.popleft()
        return PersonFilmography(FilmographyPerson(identity, 'Synthetic Person', None), ())


def controlled_hydrator(admission: UsageAdmission) -> FilmographyHydrator:
    clock = ControlledHydrationClock()
    dispatch = ProviderDispatch(admission, clock)
    return FilmographyHydrator(HydrateFilmography(ControlledFilmography(clock), ControlledFilmographyCatalog(), dispatch, clock))
