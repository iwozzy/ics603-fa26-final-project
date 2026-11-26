import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from lumiere.adapters.inbound.http.deps import HttpServices
from lumiere.adapters.outbound.clients.tmdb_filmography.client import (
    TMDBFilmographyCatalog,
)
from lumiere.adapters.outbound.persistence.pools import PoolRegistry
from lumiere.application.filmography_hydrator import FilmographyHydrator
from lumiere.application.people_writer import PeopleWriter
from lumiere.application.provider_dispatch import ProviderDispatch
from lumiere.application.use_cases.following import (
    FollowPerson,
    ListFollowing,
    UnfollowPerson,
)
from lumiere.application.use_cases.guest_identity import GuestIdentityService
from lumiere.application.use_cases.hydrate_filmography import HydrateFilmography
from lumiere.application.use_cases.search_people import SearchPeople
from lumiere.application.use_cases.usage_admission import UsageAdmissionService
from lumiere.bootstrap import AppContainer
from lumiere.domain.access import CounterKey, GuestContext, UsagePolicy
from lumiere.domain.errors import SearchFailed
from lumiere.domain.following import PersonIdentity
from lumiere.domain.people import CatalogProvider
from tests.fakes.accounting import ControlledAccess
from tests.fakes.following import MemoryFollowing
from tests.fakes.hydration import ControlledFilmography, ControlledHydrationClock
from tests.fakes.people import ControlledPeoplePersistence
from tests.fakes.search import FakeCatalog, sample_person

POLICY = UsagePolicy(*(100 for _ in range(10)))
TOTAL = CounterKey('global', 'all', 'people_provider', 'total')
GUEST = GuestContext(uuid4(), 'synthetic-ip')
FIRST = PersonIdentity(CatalogProvider.TMDB, 1)
SECOND = PersonIdentity(CatalogProvider.TMDB, 2)


@dataclass
class Runtime:
    container: AppContainer
    clock: ControlledHydrationClock
    store: ControlledFilmography
    access: ControlledAccess
    requests: list[str]
    dispose: tuple[AsyncMock, ...]
    following: MemoryFollowing


def runtime(monkeypatch: pytest.MonkeyPatch, *, attempt_timeout: float = 5) -> Runtime:
    clock = ControlledHydrationClock()
    store, access = ControlledFilmography(clock), ControlledAccess()
    admission = UsageAdmissionService(access, POLICY)
    following = MemoryFollowing()
    following.profiles.add(GUEST.profile_id)
    following.people[1] = sample_person(1)
    requests: list[str] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        admission.check_ready()
        requests.append(request.url.path)
        return httpx.Response(200, json={
            'id': int(request.url.path.rsplit('/', 1)[-1]), 'name': 'Synthetic Person',
            'movie_credits': {'cast': [], 'crew': []},
        })

    client = httpx.AsyncClient(base_url='https://provider.test', transport=httpx.MockTransport(respond))
    pools = PoolRegistry()
    dispose: dict[AsyncEngine, AsyncMock] = {}

    async def verify_disposal() -> None:
        assert not store.active and not access.active and client.is_closed
        with pytest.raises(SearchFailed, match='storage'):
            admission.check_ready()

    for name in ('application', 'people_writer', 'movie_hydration'):
        pool = pools.register(name, 'postgresql+psycopg://unused@127.0.0.1:1/unused')
        dispose[pool.engine] = AsyncMock(side_effect=verify_disposal)

    original_dispose = AsyncEngine.dispose

    async def tracked_dispose(engine: AsyncEngine, close: bool = True) -> None:
        await dispose[engine]()
        await original_dispose(engine, close)

    monkeypatch.setattr(AsyncEngine, 'dispose', tracked_dispose)
    writer = PeopleWriter(ControlledPeoplePersistence())
    dispatch = ProviderDispatch(admission, clock, rate_limit=1)
    hydrate = HydrateFilmography(
        store, TMDBFilmographyCatalog(client, clock), dispatch, clock, attempt_timeout=attempt_timeout,
    )
    hydrator = FilmographyHydrator(hydrate)
    services = HttpServices(
        SearchPeople(FakeCatalog(), admission, clock, writer),
        GuestIdentityService(access, POLICY),
        b'synthetic-test-key',
        list_following=ListFollowing(following),
        follow_person=FollowPerson(following, hydrator),
        unfollow_person=UnfollowPerson(following),
    )
    container = AppContainer(services, client, pools, admission, writer, hydrator)
    return Runtime(container, clock, store, access, requests, tuple(dispose.values()), following)


async def test_shutdown_drains_gated_work_before_closing_accounting_and_pools(monkeypatch: pytest.MonkeyPatch) -> None:
    env = runtime(monkeypatch)
    container = env.container
    hydrator = container.filmography_hydrator
    await container.startup()
    try:
        await container.services.follow_person.execute(FIRST, GUEST)
        await asyncio.wait_for(hydrator.drain(), 1)
        assert hydrator.enqueue(SECOND, GUEST)
        closing = asyncio.create_task(container.close())
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not hydrator.enqueue(PersonIdentity(CatalogProvider.TMDB, 3), GUEST)
        assert env.requests == ['/3/person/1']
        assert not closing.done() and not container.client.is_closed
        container.admission.check_ready()
        await env.clock.advance(1)
        await asyncio.wait_for(closing, 1)
        assert env.requests == ['/3/person/1', '/3/person/2']
        assert set(env.store.stored) == {FIRST, SECOND}
        assert env.access.counts[TOTAL] == 2
    finally:
        await container.close()
    assert [probe.await_count for probe in env.dispose] == [1, 1, 1]


async def test_shutdown_cancels_pending_dispatch_and_rolls_back_blocked_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    env = runtime(monkeypatch, attempt_timeout=15)
    container = env.container
    hydrator = container.filmography_hydrator
    draining = asyncio.Event()
    original_drain = hydrator.drain

    async def tracked_drain() -> None:
        draining.set()
        await original_drain()

    monkeypatch.setattr(hydrator, 'drain', tracked_drain)
    loop = asyncio.get_running_loop()
    original_time = loop.time
    elapsed = 0.0
    monkeypatch.setattr(loop, 'time', lambda: original_time() + elapsed)
    await container.startup()
    try:
        env.store.allow_commit.clear()
        assert hydrator.enqueue(FIRST, GUEST)
        assert hydrator.enqueue(SECOND, GUEST)
        assert await asyncio.wait_for(container.services.follow_person.execute(FIRST, GUEST), 1)
        assert env.following.commits == 1
        await asyncio.wait_for(env.store.committing.wait(), 1)
        assert hydrator.outstanding == 2
        closing = asyncio.create_task(container.close())
        await asyncio.wait_for(draining.wait(), 1)
        elapsed += 4.5
        await asyncio.sleep(0.001)
        assert not closing.done() and not env.store.rollbacks
        container.admission.check_ready()

        closing.cancel()
        elapsed += 0.51
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(closing, 0.25)
        assert env.store.rollbacks == 1
        assert not env.store.timestamps and not env.store.active
        assert hydrator.outstanding == hydrator.in_flight == 0
        assert env.access.counts[TOTAL] == 1
        await env.clock.advance(60)
        assert env.requests == ['/3/person/1']
    finally:
        await container.close()
    assert [probe.await_count for probe in env.dispose] == [1, 1, 1]


async def test_hydration_close_error_cannot_skip_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    env = runtime(monkeypatch)
    container = env.container
    await container.startup()
    original_close = container.filmography_hydrator.close

    async def fail() -> None:
        await original_close()
        raise RuntimeError('synthetic hydration close failure')

    monkeypatch.setattr(container.filmography_hydrator, 'close', fail)
    with pytest.raises(ExceptionGroup) as failure:
        await container.close()
    assert str(failure.value.exceptions[0]) == 'synthetic hydration close failure'
    assert container.client.is_closed
    assert [probe.await_count for probe in env.dispose] == [1, 1, 1]
