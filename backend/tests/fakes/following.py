from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self
from uuid import UUID

from lumiere.domain.following import PersonIdentity
from lumiere.domain.people import PersonSummary


class MemoryFollowing:
    def __init__(self) -> None:
        self.profiles: set[UUID] = set()
        self.people: dict[int, PersonSummary] = {}
        self.memberships: dict[tuple[UUID, int], datetime] = {}
        self.operations: list[str] = []
        self.commits = 0
        self.rollbacks = 0
        self.commit_error: Exception | None = None
        self.sequence = 0

    def __call__(self) -> 'MemoryFollowingTransaction':
        return MemoryFollowingTransaction(self)


class MemoryFollowingTransaction:
    def __init__(self, store: MemoryFollowing) -> None:
        self.store = store
        self.memberships = dict(store.memberships)
        self.follows = self
        self.committed = False

    async def __aenter__(self) -> Self:
        self.store.operations.append('enter')
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None,
                        exc: BaseException | None, tb: TracebackType | None) -> None:
        if not self.committed:
            await self.rollback()

    async def commit(self) -> None:
        self.store.operations.append('commit')
        if self.store.commit_error:
            raise self.store.commit_error
        self.store.memberships = dict(self.memberships)
        self.store.commits += 1
        self.committed = True

    async def rollback(self) -> None:
        self.store.operations.append('rollback')
        self.store.rollbacks += 1

    async def lock_profile(self, profile_id: UUID) -> bool:
        self.store.operations.append('lock_profile')
        return profile_id in self.store.profiles

    async def find_person(self, identity: PersonIdentity) -> int | None:
        self.store.operations.append('find_person')
        return next((key for key, person in self.store.people.items()
                     if (person.provider, person.provider_id) == (identity.provider, identity.provider_id)), None)

    async def is_following(self, profile_id: UUID, person_id: int) -> bool:
        self.store.operations.append('is_following')
        return (profile_id, person_id) in self.memberships

    async def count(self, profile_id: UUID) -> int:
        self.store.operations.append('count')
        return sum(owner == profile_id for owner, _ in self.memberships)

    async def add(self, profile_id: UUID, person_id: int) -> None:
        self.store.operations.append('add')
        self.store.sequence += 1
        self.memberships[profile_id, person_id] = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=self.store.sequence)

    async def list_people(self, profile_id: UUID) -> tuple[PersonSummary, ...]:
        self.store.operations.append('list_people')
        rows = sorted(((stamp, person_id) for (owner, person_id), stamp in self.memberships.items()
                       if owner == profile_id), reverse=True)
        return tuple(self.store.people[person_id] for _, person_id in rows)
