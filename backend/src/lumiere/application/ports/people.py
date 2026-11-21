from dataclasses import dataclass
from types import TracebackType
from typing import Literal, Protocol, Self

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


class PeoplePersistenceQueue(Protocol):
    def enqueue(self, people: tuple[PersonSummary, ...]) -> bool: ...


@dataclass(frozen=True)
class PeopleWriteEvent:
    kind: Literal['accepted', 'dropped', 'started', 'succeeded', 'retry', 'failed']
    outstanding: int
    in_flight: int
    attempt: int = 0
    duration_ms: int = 0
