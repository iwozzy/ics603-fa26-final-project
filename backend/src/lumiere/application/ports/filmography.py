from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Literal, Protocol, Self

from lumiere.domain.access import GuestContext
from lumiere.domain.filmography import PersonFilmography
from lumiere.domain.following import PersonIdentity


class FilmographyCatalog(Protocol):
    async def fetch(self, identity: PersonIdentity) -> PersonFilmography: ...


class FilmographyRepository(Protocol):
    async def last_hydrated(self, identity: PersonIdentity) -> datetime | None: ...
    async def upsert(self, payload: PersonFilmography) -> None: ...


class FilmographyUnitOfWork(Protocol):
    filmographies: FilmographyRepository

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type: type[BaseException] | None,
                        exc: BaseException | None, tb: TracebackType | None) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...


class FilmographyUnitOfWorkFactory(Protocol):
    def __call__(self) -> FilmographyUnitOfWork: ...


class FilmographyQueue(Protocol):
    def enqueue(self, identity: PersonIdentity, context: GuestContext) -> bool:
        """Schedule work synchronously without provider or database I/O."""
        ...


HydrationEventKind = Literal['accepted', 'coalesced', 'dropped', 'started', 'succeeded', 'failed']


@dataclass(frozen=True)
class HydrationEvent:
    kind: HydrationEventKind
    outstanding: int
    in_flight: int
    attempt: int = 0
    duration_ms: int = 0
