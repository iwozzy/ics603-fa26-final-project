from datetime import date
from uuid import UUID

from lumiere.application.ports.timeline import (
    TimelineCursorCodec,
    TimelineUnitOfWorkFactory,
)
from lumiere.domain.access import GuestContext
from lumiere.domain.errors import TimelineFailed
from lumiere.domain.timeline import (
    TimelineCursor,
    TimelineDirection,
    TimelinePage,
    TimelinePosition,
    TimelineRequest,
    TimelineSelection,
    valid_movie_id,
)


class ListTimeline:
    def __init__(self, factory: TimelineUnitOfWorkFactory, cursors: TimelineCursorCodec) -> None:
        self.factory = factory
        self.cursors = cursors

    async def execute(self, request: TimelineRequest, context: GuestContext) -> TimelinePage:
        profile_id = context.profile_id
        selection = self._selection(request, profile_id)
        async with self.factory() as uow:
            window = await uow.timeline.read(profile_id, selection)

        if any(not valid_movie_id(item.id) for item in window.items):
            raise TimelineFailed('invalid_movie_id')
        older_cursor = newer_cursor = None
        if window.has_older and window.items:
            oldest = window.items[-1]
            older_cursor = self.cursors.encode(TimelineCursor('row', oldest.release_date, oldest.id), profile_id)
        if window.has_newer:
            if selection.mode == 'initial' and window.as_of is not None:
                newer_cursor = self.cursors.encode(TimelineCursor('future_boundary', window.as_of), profile_id)
            elif window.items:
                newest = window.items[0]
                newer_cursor = self.cursors.encode(TimelineCursor('row', newest.release_date, newest.id), profile_id)
        return TimelinePage(window.items, older_cursor, newer_cursor, window.as_of, window.anchor_index)

    def _selection(self, request: TimelineRequest, profile_id: UUID) -> TimelineSelection:
        if type(request.limit) is not int or not 1 <= request.limit <= 100:
            raise TimelineFailed('invalid_request')
        if request.anchor_date is not None or request.anchor_id is not None:
            if (request.cursor is not None or request.direction is not None
                    or type(request.anchor_date) is not date
                    or not valid_movie_id(request.anchor_id)):
                raise TimelineFailed('invalid_request')
            return TimelineSelection('anchored', request.limit, TimelinePosition(request.anchor_date, request.anchor_id))
        if request.cursor is None and request.direction is None:
            return TimelineSelection('initial', request.limit)
        if type(request.cursor) is not str or request.direction not in ('older', 'newer'):
            raise TimelineFailed('invalid_request')
        return self._paging_selection(request.cursor, request.direction, request.limit, profile_id)

    def _paging_selection(
        self, token: str, direction: TimelineDirection, limit: int, profile_id: UUID,
    ) -> TimelineSelection:
        cursor = self.cursors.decode(token, profile_id)
        if cursor.kind == 'future_boundary':
            if direction != 'newer':
                raise TimelineFailed('invalid_cursor')
            return TimelineSelection('future_boundary', limit, boundary_date=cursor.release_date)
        if cursor.id is None:
            raise TimelineFailed('invalid_cursor')
        return TimelineSelection(direction, limit, TimelinePosition(cursor.release_date, cursor.id))
