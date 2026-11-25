from typing import Self, override

from lumiere.adapters.outbound.persistence.following_repository import (
    PostgresFollowingRepository,
)
from lumiere.adapters.outbound.persistence.unit_of_work import PostgresUnitOfWork
from lumiere.application.ports.following import FollowingRepository


class PostgresFollowingUnitOfWork(PostgresUnitOfWork):
    follows: FollowingRepository

    @override
    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.follows = PostgresFollowingRepository(self.session)
        return self
