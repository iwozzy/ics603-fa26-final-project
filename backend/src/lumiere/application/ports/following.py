from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from lumiere.domain.access import GuestContext
from lumiere.domain.following import FollowingSnapshot, PersonIdentity
from lumiere.domain.people import PersonSummary


class FollowingRepository(Protocol):
    async def lock_profile(self, profile_id: UUID) -> bool: ...
    async def remove(self, profile_id: UUID, identity: PersonIdentity) -> None: ...
    async def add(self, profile_id: UUID, identity: PersonIdentity) -> bool:
        """Ensure membership; return whether the local person exists, including on repeats."""
        ...
    async def list_people(self, profile_id: UUID) -> tuple[PersonSummary, ...]: ...


class FollowingUnitOfWork(Protocol):
    follows: FollowingRepository

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type: type[BaseException] | None,
                        exc: BaseException | None, tb: TracebackType | None) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...


class FollowingUnitOfWorkFactory(Protocol):
    def __call__(self) -> FollowingUnitOfWork: ...


class FollowPersonPort(Protocol):
    async def execute(self, identity: PersonIdentity, context: GuestContext) -> FollowingSnapshot: ...


class ListFollowingPort(Protocol):
    async def execute(self, context: GuestContext) -> FollowingSnapshot: ...


class UnfollowPersonPort(Protocol):
    async def execute(self, identity: PersonIdentity, context: GuestContext) -> None: ...
