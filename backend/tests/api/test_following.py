import asyncio
from dataclasses import replace

import httpx
import pytest

from lumiere.domain.errors import FollowingFailed, SearchFailed
from lumiere.main import create_app
from tests.api.conftest import Api
from tests.fakes.search import sample_person


async def bootstrap(api: Api) -> None:
    assert (await api.client.post('/api/v1/guest-session')).status_code == 200
    api.following.profiles.update(identity.profile_id for identity in api.access.tokens.values())
    for i in (4139, 2, 3, 4):
        api.following.people[i] = sample_person(i, known_for=('Alien',))


def assert_failure(response: httpx.Response) -> None:
    assert response.status_code == 500
    assert response.content == b''
    assert response.headers['cache-control'] == 'no-store'


async def test_list_empty_and_follow_exact_snapshot_without_catalog_work(api: Api) -> None:
    await bootstrap(api)
    response = await api.client.get('/api/v1/following')
    assert response.status_code == 200
    assert response.json() == {'people': [], 'limit': 3}
    assert response.headers['cache-control'] == 'no-store'
    response = await api.client.post('/api/v1/following', json={'provider': 'tmdb', 'provider_id': 4139})
    assert response.status_code == 200
    assert response.json() == {'limit': 3, 'people': [{'provider': 'tmdb', 'provider_id': 4139, 'name': 'Tom', 'known_for_department': None, 'profile_image_url': None, 'known_for': ['Alien']}]}
    assert api.following.commits == 1
    assert not api.catalog.queries and api.admission.admissions == 0


@pytest.mark.parametrize('body', [
    *({'provider': 'tmdb', 'provider_id': i} for i in (True, '4139', 1.5, 0, -1, 2**53)),
    {'provider': 'other', 'provider_id': 4139}, {}, {'provider': 'tmdb'},
    {'provider': 'tmdb', 'provider_id': 4139, 'name': 'unexpected'},
    {'provider': 'tmdb', 'provider_id': 4139, 'profile_id': 'unexpected'},
])
async def test_invalid_body_is_empty_500_without_storage(api: Api, body: object) -> None:
    await bootstrap(api)
    assert_failure(await api.client.post('/api/v1/following', json=body))
    assert api.following.operations == []


async def test_malformed_json_is_silent(api: Api) -> None:
    await bootstrap(api)
    assert_failure(await api.client.post('/api/v1/following', content='{', headers={'content-type': 'application/json'}))


async def test_missing_person_cap_and_repeat_at_three(api: Api) -> None:
    await bootstrap(api)
    assert_failure(await api.client.post('/api/v1/following', json={'provider': 'tmdb', 'provider_id': 999}))
    for i in (4139, 2, 3):
        assert (await api.client.post('/api/v1/following', json={'provider': 'tmdb', 'provider_id': i})).status_code == 200
    before = dict(api.following.memberships)
    assert_failure(await api.client.post('/api/v1/following', json={'provider': 'tmdb', 'provider_id': 4}))
    assert (await api.client.post('/api/v1/following', json={'provider': 'tmdb', 'provider_id': 4139})).status_code == 200
    assert api.following.memberships == before


async def test_cookie_ownership_and_origin(api: Api) -> None:
    await bootstrap(api)
    assert (await api.client.post('/api/v1/following', json={'provider': 'tmdb', 'provider_id': 4139})).status_code == 200
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(api.services)), base_url='https://app.test') as other:
        assert_failure(await other.get('/api/v1/following'))
        await other.post('/api/v1/guest-session')
        api.following.profiles.update(identity.profile_id for identity in api.access.tokens.values())
        assert (await other.get('/api/v1/following')).json()['people'] == []
    for headers in ({'origin': 'https://evil.test'}, {'sec-fetch-site': 'cross-site'}):
        assert_failure(await api.client.post('/api/v1/following', json={'provider': 'tmdb', 'provider_id': 2}, headers=headers))
    assert len(api.following.memberships) == 1


@pytest.mark.parametrize('error', [FollowingFailed('missing_person'), FollowingFailed('follow_limit'), FollowingFailed('session'), SearchFailed('storage'), TimeoutError(), RuntimeError('SENTINEL_ERROR')])
async def test_follow_failures_are_silent(api: Api, error: Exception) -> None:
    await bootstrap(api)
    api.following.commit_error = error
    assert_failure(await api.client.post('/api/v1/following', json={'provider': 'tmdb', 'provider_id': 4139}))
    assert not api.following.memberships


async def test_success_waits_for_commit(api: Api) -> None:
    from lumiere.domain.access import GuestContext
    from lumiere.domain.following import FollowingSnapshot, PersonIdentity
    await bootstrap(api)
    entered, release = asyncio.Event(), asyncio.Event()
    class Blocked:
        async def execute(self, identity: PersonIdentity, context: GuestContext) -> FollowingSnapshot:
            entered.set()
            await release.wait()
            return await api.services.follow_person.execute(identity, context)
    services = replace(api.services, follow_person=Blocked())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(services)), base_url='https://app.test', cookies=api.client.cookies) as client:
        task = asyncio.create_task(client.post('/api/v1/following', json={'provider': 'tmdb', 'provider_id': 4139}))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            assert not task.done() and not api.following.memberships
        finally:
            release.set()
        assert (await task).status_code == 200


def test_following_openapi_matches_silent_contract(api: Api) -> None:
    document = create_app(api.services).openapi()
    for method, operation in (('get', 'listFollowing'), ('post', 'followPerson')):
        op = document['paths']['/api/v1/following'][method]
        assert op['operationId'] == operation
        assert set(op['responses']) == {'200', '500'}
    assert 'X-Lumiere-Guest-Created' in document['paths']['/api/v1/guest-session']['post']['responses']['200']['headers']
    assert document['components']['schemas']['FollowPersonRequest']['additionalProperties'] is False
