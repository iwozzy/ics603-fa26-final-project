from types import TracebackType
from typing import Protocol, Self

from lumiere.domain.people import PersonSummary


class PeopleRepository(Protocol):
    async def upsert_batch(self, people: tuple[PersonSummary, ...]) -> None: ...


class PeopleUnitOfWork(Protocol):
    people: PeopleRepository

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...


class PeopleUnitOfWorkFactory(Protocol):
    def __call__(self) -> PeopleUnitOfWork: ...
