from types import TracebackType
from typing import Protocol, Self

from lumiere.application.ports.sessions import GuestSessionRepository
from lumiere.application.ports.usage import UsageRepository


class AccessUnitOfWork(Protocol):
    usage: UsageRepository
    sessions: GuestSessionRepository

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type: type[BaseException] | None,
                        exc: BaseException | None, tb: TracebackType | None) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> AccessUnitOfWork: ...
