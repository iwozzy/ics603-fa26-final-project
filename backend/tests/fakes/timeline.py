from types import TracebackType
from typing import Self
from uuid import UUID

from lumiere.application.ports.timeline import TimelineRepository
from lumiere.domain.timeline import TimelineSelection, TimelineWindow


class StubTimeline:
    def __init__(self, window: TimelineWindow) -> None:
        self.window = window
        self.reads: list[tuple[UUID, TimelineSelection]] = []

    def __call__(self) -> 'StubTimelineTransaction':
        return StubTimelineTransaction(self)

    async def read(self, profile_id: UUID, selection: TimelineSelection) -> TimelineWindow:
        self.reads.append((profile_id, selection))
        return self.window


class StubTimelineTransaction:
    def __init__(self, store: StubTimeline) -> None:
        self.timeline: TimelineRepository = store

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None,
                        exc: BaseException | None, tb: TracebackType | None) -> None:
        await self.rollback()

    async def commit(self) -> None:
        raise AssertionError('timeline reads must not commit')

    async def rollback(self) -> None:
        pass
