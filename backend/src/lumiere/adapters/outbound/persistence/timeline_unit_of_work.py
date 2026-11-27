from types import TracebackType
from typing import Self, override

from lumiere.adapters.outbound.persistence.timeline_repository import (
    PostgresTimelineRepository,
)
from lumiere.adapters.outbound.persistence.unit_of_work import PostgresUnitOfWork
from lumiere.application.ports.timeline import TimelineRepository
from lumiere.domain.errors import SearchFailed, TimelineFailed


class PostgresTimelineUnitOfWork(PostgresUnitOfWork):
    timeline: TimelineRepository

    @override
    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.timeline = PostgresTimelineRepository(self.session)
        return self

    @override
    async def __aexit__(self, exc_type: type[BaseException] | None,
                        exc: BaseException | None, tb: TracebackType | None) -> None:
        try:
            await super().__aexit__(exc_type, exc, tb)
        except SearchFailed as error:
            raise TimelineFailed(error.category) from None
