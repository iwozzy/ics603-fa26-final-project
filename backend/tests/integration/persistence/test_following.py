import asyncio
from collections.abc import Callable
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from lumiere.adapters.outbound.persistence.following_unit_of_work import (
    PostgresFollowingUnitOfWork,
)
from lumiere.adapters.outbound.persistence.models import (
    FollowRow,
    GuestProfileRow,
    PersonRow,
)
from lumiere.adapters.outbound.persistence.people_repository import (
    PostgresPeopleRepository,
)
from lumiere.application.use_cases.following import FollowPerson, ListFollowing
from lumiere.domain.access import GuestContext
from lumiere.domain.errors import FollowingFailed
from lumiere.domain.following import FollowingSnapshot, PersonIdentity
from lumiere.domain.people import CatalogProvider
from tests.fakes.search import sample_person

Factory = Callable[[], PostgresFollowingUnitOfWork]


def identity(i: int) -> PersonIdentity:
    return PersonIdentity(CatalogProvider.TMDB, i)


async def seed(factory: Factory) -> GuestContext:
    context = GuestContext(uuid4(), 'synthetic')
    async with factory() as uow:
        uow.session.add(GuestProfileRow(id=context.profile_id))
        await PostgresPeopleRepository(uow.session).upsert_batch(tuple(sample_person(i) for i in range(1, 5)))
        await uow.commit()
    return context


async def test_following_newest_first_and_repeat_preserves_timestamp(following_uows: Factory) -> None:
    context = await seed(following_uows)
    follow = FollowPerson(following_uows)
    for i in (1, 2, 3):
        await follow.execute(identity(i), context)
    async with following_uows() as uow:
        await uow.session.execute(text("UPDATE follows SET followed_at = '2026-01-01T00:00:00Z'"))
        rows = (await uow.session.scalars(select(PersonRow).where(PersonRow.tmdb_id.in_([2, 3])).order_by(PersonRow.id.desc()))).all()
        expected = [r.tmdb_id for r in rows] + [1]
        await uow.session.execute(text("UPDATE follows SET followed_at = '2025-01-01T00:00:00Z' WHERE person_id=(SELECT id FROM people WHERE tmdb_id=1)"))
        await uow.commit()
    async with following_uows() as uow:
        before = {r.person_id: r.followed_at for r in (await uow.session.scalars(select(FollowRow))).all()}
    result = await follow.execute(identity(1), context)
    assert [p.provider_id for p in result.people] == expected
    async with following_uows() as uow:
        assert {r.person_id: r.followed_at for r in (await uow.session.scalars(select(FollowRow))).all()} == before


async def test_two_concurrent_distinct_follows_from_two_allow_exactly_one(following_uows: Factory) -> None:
    context = await seed(following_uows)
    follow = FollowPerson(following_uows)
    for i in (1, 2):
        await follow.execute(identity(i), context)
    results = await asyncio.wait_for(asyncio.gather(*(follow.execute(identity(i), context) for i in (3, 4)), return_exceptions=True), 3)
    assert len([r for r in results if isinstance(r, FollowingSnapshot)]) == 1
    failures = [r for r in results if isinstance(r, FollowingFailed)]
    assert len(failures) == 1 and failures[0].category == 'follow_limit'
    async with following_uows() as uow:
        assert await uow.follows.count(context.profile_id) == 3


async def test_concurrent_repeat_creates_one_row(following_uows: Factory) -> None:
    context = await seed(following_uows)
    follow = FollowPerson(following_uows)
    results = await asyncio.wait_for(asyncio.gather(*(follow.execute(identity(1), context) for _ in range(2))), 3)
    assert all(len(r.people) == 1 for r in results)
    async with following_uows() as uow:
        assert await uow.follows.count(context.profile_id) == 1


async def test_following_uses_current_summary_and_profile_ownership(following_uows: Factory) -> None:
    context = await seed(following_uows)
    await FollowPerson(following_uows).execute(identity(1), context)
    async with following_uows() as uow:
        await PostgresPeopleRepository(uow.session).upsert_batch((sample_person(1, name='Updated', known_for=('Alien',), provider_profile_path='/a.jpg'),))
        await uow.commit()
    result = await ListFollowing(following_uows).execute(context)
    assert result.people[0].name == 'Updated'
    assert result.people[0].known_for == ('Alien',)
    assert result.people[0].profile_image_url == 'https://image.tmdb.org/t/p/w180_and_h180_face/a.jpg'
    assert (await ListFollowing(following_uows).execute(GuestContext(uuid4(), 'other'))).people == ()


async def test_waiting_profile_lock_yields_to_other_requests(following_uows: Factory) -> None:
    context = await seed(following_uows)
    waiting: asyncio.Task[FollowingSnapshot] | None = None
    async with following_uows() as blocker:
        assert await blocker.follows.lock_profile(context.profile_id)
        started = asyncio.Event()
        async def work() -> FollowingSnapshot:
            async with following_uows() as bounded:
                await bounded.session.execute(text("SET LOCAL lock_timeout = '2s'"))
                started.set()
                assert await bounded.follows.lock_profile(context.profile_id)
            return await FollowPerson(following_uows).execute(identity(1), context)
        waiting = asyncio.create_task(work())
        try:
            await asyncio.wait_for(started.wait(), 1)
            heartbeat = asyncio.Event()
            async def beat() -> None:
                heartbeat.set()
            await asyncio.wait_for(asyncio.gather(beat(), ListFollowing(following_uows).execute(GuestContext(uuid4(), 'other'))), .5)
            assert heartbeat.is_set() and not waiting.done()
        finally:
            waiting.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(waiting, .5)
    assert (await ListFollowing(following_uows).execute(context)).people == ()
    assert len((await FollowPerson(following_uows).execute(identity(1), context)).people) == 1


async def test_rollback_and_cancel_leave_no_membership(following_uows: Factory) -> None:
    context = await seed(following_uows)
    with pytest.raises(RuntimeError):
        async with following_uows() as uow:
            assert await uow.follows.lock_profile(context.profile_id)
            person_id = await uow.follows.find_person(identity(1))
            assert person_id is not None
            await uow.follows.add(context.profile_id, person_id)
            raise RuntimeError('rollback')
    ready = asyncio.Event()
    async def interrupted() -> None:
        async with following_uows() as uow:
            assert await uow.follows.lock_profile(context.profile_id)
            person_id = await uow.follows.find_person(identity(1))
            assert person_id is not None
            await uow.follows.add(context.profile_id, person_id)
            ready.set()
            await asyncio.Event().wait()
    task = asyncio.create_task(interrupted())
    await asyncio.wait_for(ready.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, .5)
    assert (await ListFollowing(following_uows).execute(context)).people == ()
    await FollowPerson(following_uows).execute(identity(1), context)
    # A fresh engine/connection proves durability independently of the original pool.
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from tests.integration.persistence.conftest import TEST_DATABASE_URL
    engine = create_async_engine(TEST_DATABASE_URL, hide_parameters=True)
    try:
        sessions = async_sessionmaker(engine)
        assert len((await ListFollowing(lambda: PostgresFollowingUnitOfWork(sessions)).execute(context)).people) == 1
    finally:
        await engine.dispose()
