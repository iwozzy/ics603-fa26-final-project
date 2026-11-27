import asyncio
import hashlib
import hmac
from dataclasses import replace
from datetime import date
from time import monotonic

import httpx
import pytest

from lumiere.domain.access import GuestContext
from lumiere.domain.timeline import (
    MovieSummary,
    TimelinePage,
    TimelinePosition,
    TimelineRequest,
    TimelineSelection,
    TimelineWindow,
)
from lumiere.main import create_app
from tests.api.conftest import Api

PATH = '/api/v1/timeline'
AS_OF = date(2026, 11, 26)
MOVIE = MovieSummary(123, 'Bullet Train', None, None, date(2022, 8, 3))


def assert_failure(response: httpx.Response) -> None:
    assert response.status_code == 500
    assert response.content == b''
    assert response.headers['cache-control'] == 'no-store'


async def test_empty_initial_window_has_utc_boundary_and_default_limit(api: Api) -> None:
    assert (await api.client.post('/api/v1/guest-session')).status_code == 200
    profile_id = next(iter(api.access.tokens.values())).profile_id
    response = await api.client.get(PATH)
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.json() == {
        'items': [], 'older_cursor': None, 'newer_cursor': None,
        'as_of': '2026-11-26', 'anchor_index': None,
    }
    assert api.timeline.reads == [(profile_id, TimelineSelection('initial', 20))]
    assert api.catalog.queries == [] and api.admission.admissions == 0


async def test_anchored_and_paging_responses_serialize_movie_and_metadata(api: Api) -> None:
    await api.client.post('/api/v1/guest-session')
    profile_id = next(iter(api.access.tokens.values())).profile_id
    api.timeline.window = TimelineWindow((MOVIE,), True, False, AS_OF, 0)
    response = await api.client.get(f'{PATH}?anchor_date=2022-08-03&anchor_id=123&limit=100')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    anchored = response.json()
    assert anchored['items'] == [{
        'id': 123, 'title': 'Bullet Train', 'overview': None,
        'poster_image_url': None, 'release_date': '2022-08-03',
    }]
    assert type(anchored['items'][0]['id']) is int
    assert anchored['anchor_index'] == 0 and anchored['as_of'] == '2026-11-26'
    assert anchored['newer_cursor'] is None
    assert isinstance(anchored['older_cursor'], str)
    assert api.timeline.reads == [
        (profile_id, TimelineSelection('anchored', 100, TimelinePosition(date(2022, 8, 3), 123))),
    ]

    api.timeline.window = TimelineWindow((), False, False, None, None)
    response = await api.client.get(PATH, params={'cursor': anchored['older_cursor'], 'direction': 'older', 'limit': '1'})
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.json() == {
        'items': [], 'older_cursor': None, 'newer_cursor': None, 'as_of': None, 'anchor_index': None,
    }
    assert api.timeline.reads[1:] == [
        (profile_id, TimelineSelection('older', 1, TimelinePosition(date(2022, 8, 3), 123))),
    ]


async def test_timeline_passes_verified_guest_and_hashed_peer_to_service(api: Api) -> None:
    requests: list[tuple[TimelineRequest, GuestContext]] = []

    class RecordingTimeline:
        async def execute(self, request: TimelineRequest, context: GuestContext) -> TimelinePage:
            requests.append((request, context))
            return TimelinePage((), None, None, AS_OF, None)

    services = replace(api.services, list_timeline=RecordingTimeline())
    transport = httpx.ASGITransport(app=create_app(services), client=('203.0.113.11', 1234))
    async with httpx.AsyncClient(transport=transport, base_url='https://app.test') as client:
        await client.post('/api/v1/guest-session')
        assert (await client.get(PATH, headers={'X-Forwarded-For': '203.0.113.12'})).status_code == 200
        client.cookies.clear()
        await client.post('/api/v1/guest-session')
        assert (await client.get(PATH)).status_code == 200
    ip_key = hmac.new(services.ip_hash_key, b'203.0.113.11', hashlib.sha256).hexdigest()
    first, second = (identity.profile_id for identity in api.access.tokens.values())
    assert first != second
    assert requests == [
        (TimelineRequest(), GuestContext(first, ip_key)),
        (TimelineRequest(), GuestContext(second, ip_key)),
    ]


@pytest.mark.parametrize('query', [
    'profile_id=unexpected',
    'anchor_date=2022-08-03',
    'anchor_id=123',
    'anchor_date=2022-08-03T00:00:00&anchor_id=123',
    'anchor_date=2022-08-03&anchor_id=1.0',
    'anchor_date=2022-08-03&anchor_id=0',
    'anchor_date=2022-08-03&anchor_id=9007199254740992',
    'cursor=opaque',
    'direction=older',
    'cursor=opaque&direction=sideways',
    'cursor=opaque&direction=older&anchor_date=2022-08-03&anchor_id=123',
    'cursor=bad!&direction=older',
    'limit=0',
    'limit=101',
])
async def test_invalid_query_has_empty_500_without_timeline_read(api: Api, query: str) -> None:
    await api.client.post('/api/v1/guest-session')
    assert_failure(await api.client.get(f'{PATH}?{query}'))
    assert api.timeline.reads == []
    assert api.catalog.queries == [] and api.admission.admissions == 0


async def test_missing_guest_has_empty_500_without_query_or_provider_work(api: Api) -> None:
    assert_failure(await api.client.get(PATH))
    assert api.timeline.reads == []
    assert api.access.rollbacks == 0 and api.access.commits == 0
    assert api.catalog.queries == [] and api.admission.admissions == 0


@pytest.mark.parametrize('movie_id', [0, 9007199254740992, True])
async def test_response_rejects_unsafe_movie_id(api: Api, movie_id: int) -> None:
    class BadTimeline:
        async def execute(self, request: TimelineRequest, context: GuestContext) -> TimelinePage:
            return TimelinePage((replace(MOVIE, id=movie_id),), None, None, AS_OF, None)

    app = create_app(replace(api.services, list_timeline=BadTimeline()))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://app.test') as client:
        await client.post('/api/v1/guest-session')
        assert_failure(await client.get(PATH))


async def test_timeline_returns_at_deadline_during_cancellation_cleanup(api: Api) -> None:
    cancelled, release, cleaned = asyncio.Event(), asyncio.Event(), asyncio.Event()

    class SlowTimeline:
        async def execute(self, request: TimelineRequest, context: GuestContext) -> TimelinePage:
            try:
                await asyncio.sleep(9)
            except asyncio.CancelledError:
                cancelled.set()
                await release.wait()
            cleaned.set()
            return TimelinePage((), None, None, AS_OF, None)

    app = create_app(replace(api.services, list_timeline=SlowTimeline()))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://app.test') as client:
        await client.post('/api/v1/guest-session')
        start = monotonic()
        try:
            response = await asyncio.wait_for(client.get(PATH), 8)
            assert_failure(response)
            assert 6.9 <= monotonic() - start < 8
            assert cancelled.is_set() and not cleaned.is_set()
        finally:
            release.set()
        await asyncio.wait_for(cleaned.wait(), 1)
