from datetime import datetime
from types import TracebackType
from typing import Protocol, Self

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
