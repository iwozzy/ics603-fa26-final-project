from typing import Self, override

from lumiere.adapters.outbound.persistence.people_repository import (
    PostgresPeopleRepository,
)
from lumiere.adapters.outbound.persistence.unit_of_work import PostgresUnitOfWork
from lumiere.application.ports.people import PeopleRepository


class PostgresPeopleUnitOfWork(PostgresUnitOfWork):
    people: PeopleRepository

    @override
    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.people = PostgresPeopleRepository(self.session)
        return self
