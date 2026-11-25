import asyncio
from types import TracebackType
from typing import Self, override

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lumiere.adapters.outbound.persistence.repositories import (
    PostgresGuestIdentityRepository,
    PostgresUsageRepository,
)
from lumiere.application.ports.guests import GuestIdentityRepository
from lumiere.application.ports.usage import UsageRepository
from lumiere.domain.errors import SearchFailed


class PostgresUnitOfWork:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.factory = sessions

    async def __aenter__(self) -> Self:
        self.session = self.factory()
        await self.session.begin()
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        try:
            if isinstance(exc, asyncio.CancelledError):
                # Psycopg closes its socket locally on invalidation, letting
                # Postgres roll back, without awaiting a network rollback ACK.
                await self.session.invalidate()
            else:
                if self.session.in_transaction():
                    await self.rollback()
                await self.session.close()
        except asyncio.CancelledError:
            await self.session.invalidate()
            raise
        except SQLAlchemyError:
            await self.session.invalidate()
            raise SearchFailed("storage") from None
        if isinstance(exc, SQLAlchemyError):
            raise SearchFailed("storage") from None

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


class PostgresAccessUnitOfWork(PostgresUnitOfWork):
    usage: UsageRepository
    guests: GuestIdentityRepository

    @override
    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.usage = PostgresUsageRepository(self.session)
        self.guests = PostgresGuestIdentityRepository(self.session)
        return self
