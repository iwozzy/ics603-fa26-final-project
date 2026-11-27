from datetime import date, datetime
from typing import cast
from uuid import UUID

import pytest

from lumiere.adapters.inbound.http.timeline_cursor import Base64TimelineCursorCodec
from lumiere.application.use_cases.list_timeline import ListTimeline
from lumiere.domain.access import GuestContext
from lumiere.domain.errors import TimelineFailed
from lumiere.domain.timeline import (
    MovieSummary,
    TimelineCursor,
    TimelineDirection,
    TimelinePosition,
    TimelineRequest,
    TimelineSelection,
    TimelineWindow,
)
from tests.fakes.timeline import StubTimeline

CONTEXT = GuestContext(UUID(int=1), 'synthetic-ip')
PRESENT = date(2026, 1, 2)
MOVIES = (
    MovieSummary(9, 'Newer', None, None, date(2025, 1, 1)),
    MovieSummary(3, 'Older', None, None, date(2024, 1, 1)),
)


async def test_initial_uses_resolved_profile_and_emits_cursor_for_each_available_side() -> None:
    store = StubTimeline(TimelineWindow(MOVIES, True, True, PRESENT, None))
    cursors = Base64TimelineCursorCodec()

    page = await ListTimeline(store, cursors).execute(TimelineRequest(), CONTEXT)

    assert store.reads == [(CONTEXT.profile_id, TimelineSelection('initial', 20))]
    assert page.items == MOVIES
    assert page.as_of == PRESENT and page.anchor_index is None
    assert page.older_cursor and page.newer_cursor
    assert cursors.decode(page.older_cursor, CONTEXT.profile_id) == TimelineCursor('row', date(2024, 1, 1), 3)
    assert cursors.decode(page.newer_cursor, CONTEXT.profile_id) == TimelineCursor('future_boundary', PRESENT)


@pytest.mark.parametrize('direction', ['older', 'newer'])
async def test_row_cursor_uses_its_encoded_position(direction: str) -> None:
    store = StubTimeline(TimelineWindow(MOVIES, True, True, None, None))
    cursors = Base64TimelineCursorCodec()
    token = cursors.encode(TimelineCursor('row', PRESENT, 11), CONTEXT.profile_id)

    page = await ListTimeline(store, cursors).execute(
        TimelineRequest(limit=2, cursor=token, direction=cast(TimelineDirection, direction)), CONTEXT,
    )

    mode = cast(TimelineDirection, direction)
    assert store.reads == [(CONTEXT.profile_id, TimelineSelection(mode, 2, TimelinePosition(PRESENT, 11)))]
    assert page.as_of is None and page.anchor_index is None
    assert page.older_cursor and page.newer_cursor
    assert cursors.decode(page.older_cursor, CONTEXT.profile_id) == TimelineCursor('row', date(2024, 1, 1), 3)
    assert cursors.decode(page.newer_cursor, CONTEXT.profile_id) == TimelineCursor('row', date(2025, 1, 1), 9)


async def test_future_boundary_uses_encoded_date_even_when_result_is_empty() -> None:
    store = StubTimeline(TimelineWindow((), False, False, None, None))
    cursors = Base64TimelineCursorCodec()
    token = cursors.encode(TimelineCursor('future_boundary', PRESENT), CONTEXT.profile_id)

    page = await ListTimeline(store, cursors).execute(TimelineRequest(cursor=token, direction='newer'), CONTEXT)

    assert store.reads == [(CONTEXT.profile_id, TimelineSelection('future_boundary', 20, boundary_date=PRESENT))]
    assert page.items == ()
    assert page.older_cursor is None and page.newer_cursor is None
    assert page.as_of is None and page.anchor_index is None


async def test_anchor_uses_inclusive_older_position_and_returns_anchor_metadata() -> None:
    store = StubTimeline(TimelineWindow(MOVIES, False, False, PRESENT, 1))
    request = TimelineRequest(limit=100, anchor_date=date(2024, 1, 1), anchor_id=3)

    page = await ListTimeline(store, Base64TimelineCursorCodec()).execute(request, CONTEXT)

    assert store.reads == [(CONTEXT.profile_id, TimelineSelection('anchored', 100, TimelinePosition(date(2024, 1, 1), 3)))]
    assert page.items == MOVIES
    assert page.as_of == PRESENT and page.anchor_index == 1
    assert page.older_cursor is None and page.newer_cursor is None


@pytest.mark.parametrize('request_value', [
    TimelineRequest(limit=cast(int, True)),
    TimelineRequest(limit=cast(int, 1.5)),
    TimelineRequest(limit=0),
    TimelineRequest(limit=101),
    TimelineRequest(cursor='token'),
    TimelineRequest(direction='older'),
    TimelineRequest(cursor='token', direction=cast(TimelineDirection, 'unknown')),
    TimelineRequest(anchor_id=1),
    TimelineRequest(anchor_date=PRESENT),
    TimelineRequest(anchor_date=datetime(2026, 1, 2), anchor_id=1),
    TimelineRequest(anchor_date=PRESENT, anchor_id=cast(int, True)),
    TimelineRequest(anchor_date=PRESENT, anchor_id=0),
    TimelineRequest(anchor_date=PRESENT, anchor_id=9007199254740992),
    TimelineRequest(cursor='token', direction='older', anchor_date=PRESENT, anchor_id=1),
])
async def test_invalid_request_fails_before_reading(request_value: TimelineRequest) -> None:
    store = StubTimeline(TimelineWindow((), False, False, PRESENT, None))
    with pytest.raises(TimelineFailed, match='invalid_request'):
        await ListTimeline(store, Base64TimelineCursorCodec()).execute(request_value, CONTEXT)
    assert store.reads == []


async def test_future_boundary_rejects_older_direction() -> None:
    store = StubTimeline(TimelineWindow((), False, False, None, None))
    cursors = Base64TimelineCursorCodec()
    token = cursors.encode(TimelineCursor('future_boundary', PRESENT), CONTEXT.profile_id)

    with pytest.raises(TimelineFailed, match='invalid_cursor'):
        await ListTimeline(store, cursors).execute(TimelineRequest(cursor=token, direction='older'), CONTEXT)
    assert store.reads == []


async def test_unsafe_movie_id_fails_even_without_cursors() -> None:
    movie = MovieSummary(9007199254740992, 'Invalid', None, None, PRESENT)
    store = StubTimeline(TimelineWindow((movie,), False, False, PRESENT, None))

    with pytest.raises(TimelineFailed, match='invalid_movie_id'):
        await ListTimeline(store, Base64TimelineCursorCodec()).execute(TimelineRequest(), CONTEXT)
