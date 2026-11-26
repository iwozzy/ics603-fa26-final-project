import asyncio
from typing import cast
from uuid import uuid4

import httpx
import pytest

from lumiere.adapters.inbound.http.deps import HttpServices
from lumiere.adapters.outbound.persistence.pools import PoolRegistry
from lumiere.application.people_writer import PeopleWriter
from lumiere.application.use_cases.following import (
    FollowPerson,
    ListFollowing,
    UnfollowPerson,
)
from lumiere.application.use_cases.guest_identity import GuestIdentityService
from lumiere.application.use_cases.search_people import SearchPeople
from lumiere.application.use_cases.usage_admission import UsageAdmissionService
from lumiere.bootstrap import AppContainer
from lumiere.domain.access import GuestContext, UsagePolicy
from lumiere.domain.errors import SearchFailed
from tests.fakes.accounting import ControlledAccess
from tests.fakes.following import MemoryFollowing
from tests.fakes.hydration import controlled_hydrator
from tests.fakes.people import ControlledPeoplePersistence
from tests.fakes.search import FakeCatalog, FakeClock, sample_person

POLICY = UsagePolicy(*(100 for _ in range(10)))


class PoolsProbe:
    def __init__(self, access: ControlledAccess, people: ControlledPeoplePersistence) -> None:
        self.access, self.people = access, people
        self.closed = False
        self.calls = 0

    async def close(self) -> None:
        assert not self.access.active and not self.people.active_session_tokens
        self.closed = True
        self.calls += 1


def container_for(access: ControlledAccess, people: ControlledPeoplePersistence) -> tuple[AppContainer, PoolsProbe]:
    admission = UsageAdmissionService(access, POLICY, shutdown_timeout=.03)
    writer = PeopleWriter(people, shutdown_timeout=.03)
    pools = PoolsProbe(access, people)
    hydration = controlled_hydrator(admission)
    services = HttpServices(SearchPeople(FakeCatalog(), admission, FakeClock(), writer), GuestIdentityService(access, POLICY), b'synthetic-test-key', list_following=ListFollowing(MemoryFollowing()), follow_person=FollowPerson(MemoryFollowing(), hydration), unfollow_person=UnfollowPerson(MemoryFollowing()))
    return AppContainer(services, httpx.AsyncClient(), cast(PoolRegistry, pools), admission, writer, hydration), pools


async def test_both_writers_finish_before_pool_disposal_and_close_is_repeatable() -> None:
    access, people = ControlledAccess(), ControlledPeoplePersistence()
    container, pools = container_for(access, people)
    await container.startup()
    access.allow_flush.clear()
    people.allow_commit.clear()
    await container.admission.admit_and_charge(GuestContext(uuid4(), 'synthetic'), FakeClock().now())
    assert container.people_writer.enqueue((sample_person(),))
    await asyncio.wait_for(asyncio.gather(access.entered.wait(), people.committing.wait()), 1)
    await asyncio.wait_for(container.close(), .5)
    await container.close()
    assert pools.closed and container.client.is_closed and pools.calls == 1
    assert container.people_writer.outstanding == 0


async def test_blocked_people_write_does_not_block_accounting() -> None:
    access, people = ControlledAccess(), ControlledPeoplePersistence()
    container, pools = container_for(access, people)
    await container.startup()
    people.allow_commit.clear()
    try:
        container.people_writer.enqueue((sample_person(),))
        await asyncio.wait_for(people.committing.wait(), 1)
        await container.admission.admit_and_charge(GuestContext(uuid4(), 'synthetic'), FakeClock().now())
        await asyncio.wait_for(container.admission.drain(), 1)
        assert access.counts and people.commits == 0
        assert not pools.closed
    finally:
        await container.close()


async def test_partial_startup_hydration_failure_cleans_every_resource(monkeypatch: pytest.MonkeyPatch) -> None:
    access, people = ControlledAccess(), ControlledPeoplePersistence()
    container, pools = container_for(access, people)
    async def fail(now: object) -> None:
        raise SearchFailed('storage')
    monkeypatch.setattr(container.admission, 'start', fail)
    with pytest.raises(SearchFailed):
        await container.startup()
    await container.close()
    assert pools.closed and container.client.is_closed
    assert not container.people_writer.enqueue((sample_person(),))
    assert people.attempts == 0


async def test_one_writer_close_error_does_not_skip_other_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    access, people = ControlledAccess(), ControlledPeoplePersistence()
    container, pools = container_for(access, people)
    await container.startup()
    original = container.admission.close
    async def fail() -> None:
        await original()
        raise RuntimeError('synthetic')
    monkeypatch.setattr(container.admission, 'close', fail)
    with pytest.raises(ExceptionGroup):
        await container.close()
    assert pools.closed and container.client.is_closed
    assert not container.people_writer.enqueue((sample_person(),))


async def test_cancelling_container_close_waits_for_writers_before_disposal() -> None:
    access, people = ControlledAccess(), ControlledPeoplePersistence()
    container, pools = container_for(access, people)
    await container.startup()
    people.allow_commit.clear()
    container.people_writer.enqueue((sample_person(),))
    await asyncio.wait_for(people.committing.wait(), 1)
    closing = asyncio.create_task(container.close())
    await asyncio.sleep(0)
    closing.cancel()
    with pytest.raises(asyncio.CancelledError):
        await closing
    assert pools.closed and container.client.is_closed
    assert not people.active_session_tokens


async def test_runtime_assigns_distinct_named_factories_and_instruments_all(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import SecretStr
    from sqlalchemy import Engine

    from lumiere import bootstrap
    from lumiere.config import Settings
    engines: list[Engine] = []
    monkeypatch.setattr(bootstrap, 'instrument_database', engines.append)
    # model_construct bypasses all environment discovery; values are test-only.
    settings = Settings.model_construct(_fields_set=None, database_url=SecretStr('postgresql+psycopg://unused@127.0.0.1:1/unused'), tmdb_access_token=SecretStr('synthetic'), ip_hash_key=SecretStr('synthetic'), **{name: 100 for name in UsagePolicy.__dataclass_fields__})
    container = bootstrap.build_container(settings)
    application = container.pools.get('application')
    people = container.pools.get('people_writer')
    hydration = container.pools.get('movie_hydration')
    try:
        assert len({application.engine, people.engine, hydration.engine}) == 3
        assert engines == [application.engine.sync_engine, people.engine.sync_engine, hydration.engine.sync_engine]
        assert container.services.follow_person.inner.factory().factory is application.sessions  # type: ignore[attr-defined]
        assert container.services.list_following.inner.factory().factory is application.sessions  # type: ignore[attr-defined]
        assert container.services.unfollow_person.inner.factory().factory is application.sessions  # type: ignore[attr-defined]
        assert container.admission.uow_factory().factory is application.sessions  # type: ignore[attr-defined]
        assert container.people_writer.uow_factory().factory is people.sessions  # type: ignore[attr-defined]
        assert container.filmography_hydrator.hydrate.factory().factory is hydration.sessions  # type: ignore[attr-defined]
        assert container.services.follow_person.inner.hydration is container.filmography_hydrator  # type: ignore[attr-defined]
        assert container.filmography_hydrator.hydrate.catalog.inner.client is container.client  # type: ignore[attr-defined]
        assert container.filmography_hydrator.hydrate.dispatch._admission is container.admission
        for pool in (application, people, hydration):
            assert pool.engine.pool.size() == 5  # type: ignore[attr-defined]
            assert pool.engine.pool._max_overflow == 5  # type: ignore[attr-defined]
            assert pool.engine.pool.checkedout() == 0  # type: ignore[attr-defined]
    finally:
        await container.close()
