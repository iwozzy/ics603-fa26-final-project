from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from lumiere.domain.access import GuestContext
from lumiere.domain.timeline import (
    TimelineCursor,
    TimelinePage,
    TimelineRequest,
    TimelineSelection,
    TimelineWindow,
)


class ListTimelinePort(Protocol):
    async def execute(self, request: TimelineRequest, context: GuestContext) -> TimelinePage: ...


class TimelineRepository(Protocol):
    async def read(self, profile_id: UUID, selection: TimelineSelection) -> TimelineWindow: ...


class TimelineUnitOfWork(Protocol):
    timeline: TimelineRepository

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type: type[BaseException] | None,
                        exc: BaseException | None, tb: TracebackType | None) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...


class TimelineUnitOfWorkFactory(Protocol):
    def __call__(self) -> TimelineUnitOfWork: ...


class TimelineCursorCodec(Protocol):
    def encode(self, cursor: TimelineCursor, profile_id: UUID) -> str: ...
    def decode(self, token: str, profile_id: UUID) -> TimelineCursor: ...
