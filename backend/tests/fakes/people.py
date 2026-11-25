import asyncio
from types import TracebackType
from typing import Self

from lumiere.application.ports.people import PeopleRepository
from lumiere.domain.people import PersonSummary


class ControlledPeoplePersistence:
    def __init__(self) -> None:
        self.batches: list[tuple[PersonSummary, ...]] = []
        self.active_session_tokens: set[object] = set()
        self.max_active = 0
        self.attempts = 0
        self.commits = 0
        self.rollbacks = 0
        self.entered: dict[int, asyncio.Event] = {}
        self.releases: dict[int, asyncio.Event] = {}
        self.allow_commit = asyncio.Event()
        self.allow_commit.set()
        self.committing = asyncio.Event()
        self.upsert_errors: list[Exception] = []
        self.commit_errors: list[Exception] = []
        self.ack_losses = 0

    def barrier(self, identifier: int) -> asyncio.Event:
        return self.releases.setdefault(identifier, asyncio.Event())

    def entry(self, identifier: int) -> asyncio.Event:
        return self.entered.setdefault(identifier, asyncio.Event())

    def __call__(self) -> 'ControlledPeopleUow':
        self.attempts += 1
        return ControlledPeopleUow(self)


class ControlledPeopleUow:
    def __init__(self, store: ControlledPeoplePersistence) -> None:
        self.store = store
        self.people: PeopleRepository = self
        self.token = object()
        self.committed = False

    async def __aenter__(self) -> Self:
        self.store.active_session_tokens.add(self.token)
        self.store.max_active = max(self.store.max_active, len(self.store.active_session_tokens))
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        if exc is not None or not self.committed:
            await self.rollback()
        self.store.active_session_tokens.remove(self.token)

    async def upsert_batch(self, people: tuple[PersonSummary, ...]) -> None:
        self.store.batches.append(people)
        identifier = people[0].provider_id
        self.store.entry(identifier).set()
        if identifier in self.store.releases:
            await self.store.releases[identifier].wait()
        if self.store.upsert_errors:
            raise self.store.upsert_errors.pop(0)

    async def commit(self) -> None:
        self.store.committing.set()
        await self.store.allow_commit.wait()
        if self.store.commit_errors:
            raise self.store.commit_errors.pop(0)
        self.store.commits += 1
        self.committed = True
        if self.store.ack_losses:
            self.store.ack_losses -= 1
            raise RuntimeError('synthetic ACK loss')

    async def rollback(self) -> None:
        self.store.rollbacks += 1
