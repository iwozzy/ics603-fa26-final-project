import asyncio
from types import TracebackType
from typing import Self

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lumiere.adapters.outbound.persistence.repositories import (
    PostgresGuestSessionRepository,
    PostgresUsageRepository,
)
from lumiere.application.ports.sessions import GuestSessionRepository
from lumiere.application.ports.usage import UsageRepository
from lumiere.domain.errors import SearchFailed


class PostgresAccessUnitOfWork:
    usage: UsageRepository
    sessions: GuestSessionRepository

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.factory = sessions

    async def __aenter__(self) -> Self:
        self.session = self.factory()
        await self.session.begin()
        self.usage = PostgresUsageRepository(self.session)
        self.sessions = PostgresGuestSessionRepository(self.session)
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        try:
            if self.session.in_transaction():
                await asyncio.shield(self.rollback())
        finally:
            await asyncio.shield(self.session.close())
        if isinstance(exc, SQLAlchemyError):
            raise SearchFailed("storage") from None

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
