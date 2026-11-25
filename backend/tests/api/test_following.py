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


@pytest.mark.parametrize('method', ['POST', 'DELETE'])
@pytest.mark.parametrize('body', [
    *({'provider': 'tmdb', 'provider_id': i} for i in (True, '4139', 1.5, 0, -1, 2**53)),
    {'provider': 'other', 'provider_id': 4139}, {}, {'provider': 'tmdb'},
    {'provider': 'tmdb', 'provider_id': 4139, 'name': 'unexpected'},
    {'provider': 'tmdb', 'provider_id': 4139, 'profile_id': 'unexpected'},
])
async def test_invalid_body_is_empty_500_without_storage(api: Api, body: object, method: str) -> None:
    await bootstrap(api)
    assert_failure(await api.client.request(method, '/api/v1/following', json=body))
    assert api.following.operations == []


@pytest.mark.parametrize('method', ['POST', 'DELETE'])
@pytest.mark.parametrize('content', [b'{', b'\xff \xff'])
async def test_malformed_json_is_silent(api: Api, method: str, content: bytes) -> None:
    await bootstrap(api)
    assert_failure(await api.client.request(method, '/api/v1/following', content=content, headers={'content-type': 'application/json'}))


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
    for method, operation in (('get', 'listFollowing'), ('post', 'followPerson'), ('delete', 'unfollowPerson')):
        op = document['paths']['/api/v1/following'][method]
        assert op['operationId'] == operation
        assert set(op['responses']) == ({'204', '500'} if method == 'delete' else {'200', '500'})
        if method == 'delete':
            assert 'content' not in op['responses']['204']
            assert op['requestBody']['required'] is True
            assert set(op['requestBody']['content']) == {'application/json'}
    assert 'X-Lumiere-Guest-Created' in document['paths']['/api/v1/guest-session']['post']['responses']['200']['headers']
    assert document['components']['schemas']['FollowPersonRequest']['additionalProperties'] is False


@pytest.mark.parametrize('method', ['POST', 'DELETE'])
@pytest.mark.parametrize('undecodable', [False, True])
async def test_validation_has_sanitized_http_category(api: Api, monkeypatch: pytest.MonkeyPatch, undecodable: bool, method: str) -> None:
    from collections.abc import Iterator
    from contextlib import contextmanager

    from lumiere import observability
    spans: list[tuple[str, dict[str, str | int]]] = []
    @contextmanager
    def capture(name: str) -> Iterator[dict[str, str | int]]:
        attributes: dict[str, str | int] = {}
        spans.append((name, attributes))
        yield attributes
    monkeypatch.setattr(observability, 'safe_span', capture)
    app = create_app(api.services)
    observability.instrument_http(app)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://app.test') as client:
        if undecodable:
            response = await client.request(method, '/api/v1/following', content=b'\xff \xff', headers={'content-type': 'application/json'})
        else:
            response = await client.request(method, '/api/v1/following', json={'provider': 'SENTINEL_INVALID', 'provider_id': True})
        assert_failure(response)
    assert any(name == ('http.following.follow' if method == 'POST' else 'http.following.unfollow') and attributes.get('failure_category') == 'invalid_identity' for name, attributes in spans)
    assert 'SENTINEL' not in str(spans)


async def test_delete_following_is_empty_204_and_idempotent(api: Api) -> None:
    await bootstrap(api)
    body = {'provider': 'tmdb', 'provider_id': 4139}
    assert (await api.client.post('/api/v1/following', json=body)).status_code == 200
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(api.services)), base_url='https://app.test') as other:
        await other.post('/api/v1/guest-session')
        api.following.profiles.update(i.profile_id for i in api.access.tokens.values())
        assert (await other.post('/api/v1/following', json=body)).status_code == 200
        for i in (4139, 4139, 999):
            response = await api.client.request('DELETE', '/api/v1/following', json={'provider': 'tmdb', 'provider_id': i})
            assert response.status_code == 204
            assert response.content == b''
            assert 'content-type' not in response.headers
            assert response.headers['cache-control'] == 'no-store'
        assert len((await other.get('/api/v1/following')).json()['people']) == 1
    assert (await api.client.get('/api/v1/following')).json()['people'] == []
    assert not api.catalog.queries and api.admission.admissions == 0


@pytest.mark.parametrize('error', [FollowingFailed('session'), SearchFailed('storage'), TimeoutError(), RuntimeError('SENTINEL_ERROR')])
async def test_delete_commit_failures_preserve_membership(api: Api, error: Exception) -> None:
    await bootstrap(api)
    body = {'provider': 'tmdb', 'provider_id': 4139}
    await api.client.post('/api/v1/following', json=body)
    before = dict(api.following.memberships)
    api.following.commit_error = error
    assert_failure(await api.client.request('DELETE', '/api/v1/following', json=body))
    assert api.following.memberships == before
    assert not api.catalog.queries and api.admission.admissions == 0


async def test_delete_session_and_origin_failures_are_silent(api: Api) -> None:
    body = {'provider': 'tmdb', 'provider_id': 4139}
    assert_failure(await api.client.request('DELETE', '/api/v1/following', json=body))
    await bootstrap(api)
    await api.client.post('/api/v1/following', json=body)
    before = dict(api.following.memberships)
    for headers in ({'origin': 'https://evil.test'}, {'sec-fetch-site': 'cross-site'}):
        assert_failure(await api.client.request('DELETE', '/api/v1/following', json=body, headers=headers))
    assert api.following.memberships == before


async def test_delete_success_waits_for_commit(api: Api) -> None:
    from typing import override

    from lumiere.application.use_cases.following import UnfollowPerson
    from tests.fakes.following import MemoryFollowingTransaction
    await bootstrap(api)
    body = {'provider': 'tmdb', 'provider_id': 4139}
    await api.client.post('/api/v1/following', json=body)
    entered, release = asyncio.Event(), asyncio.Event()
    class BlockedCommit(MemoryFollowingTransaction):
        @override
        async def commit(self) -> None:
            entered.set()
            await release.wait()
            await super().commit()
    services = replace(api.services, unfollow_person=UnfollowPerson(lambda: BlockedCommit(api.following)))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(services)), base_url='https://app.test', cookies=api.client.cookies) as client:
        task = asyncio.create_task(client.request('DELETE', '/api/v1/following', json=body))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            assert not task.done() and len(api.following.memberships) == 1
        finally:
            release.set()
        assert (await task).status_code == 204
    assert not api.following.memberships


async def test_delete_resolved_guest_with_missing_profile_is_empty_204(api: Api) -> None:
    await bootstrap(api)
    api.following.profiles.clear()
    response = await api.client.request('DELETE', '/api/v1/following', json={'provider': 'tmdb', 'provider_id': 4139})
    assert response.status_code == 204
    assert response.content == b''
    assert 'content-type' not in response.headers
    assert response.headers['cache-control'] == 'no-store'
    assert api.following.commits == 1
    assert not api.catalog.queries and api.admission.admissions == 0
