from typing import Self, override

from lumiere.adapters.outbound.persistence.filmography_repository import (
    PostgresFilmographyRepository,
)
from lumiere.adapters.outbound.persistence.unit_of_work import PostgresUnitOfWork
from lumiere.application.ports.filmography import FilmographyRepository


class PostgresFilmographyUnitOfWork(PostgresUnitOfWork):
    filmographies: FilmographyRepository

    @override
    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.filmographies = PostgresFilmographyRepository(self.session)
        return self
