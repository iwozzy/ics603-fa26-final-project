import asyncio
from collections.abc import Callable
from typing import Self, override
from uuid import uuid4

import pytest
from sqlalchemy import event, select, text

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
from lumiere.application.use_cases.following import (
    FollowPerson,
    ListFollowing,
    UnfollowPerson,
)
from lumiere.domain.access import GuestContext
from lumiere.domain.errors import FollowingFailed
from lumiere.domain.following import FollowingSnapshot, PersonIdentity
from lumiere.domain.people import CatalogProvider
from tests.fakes.hydration import RecordingFilmographyQueue
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


@pytest.mark.parametrize(('existing', 'target', 'failure', 'expected'), [
    ((), 4, None, [4]),
    ((1, 2, 3), 1, None, [3, 2, 1]),
    ((1, 2, 3), 4, 'follow_limit', [3, 2, 1]),
])
async def test_follow_uses_three_statements(
    following_uows: Factory, existing: tuple[int, ...], target: int,
    failure: str | None, expected: list[int],
) -> None:
    context = await seed(following_uows)
    follow = FollowPerson(following_uows, RecordingFilmographyQueue())
    for i in existing:
        await follow.execute(identity(i), context)
    statements: list[str] = []
    def capture(*args: object) -> None:
        statements.append(str(args[2]))
    async with following_uows() as observer:
        connection = await observer.session.connection()
        sync_connection = connection.sync_connection
        assert sync_connection is not None
        engine = sync_connection.engine
        event.listen(engine, 'before_cursor_execute', capture)
        try:
            if failure is None:
                result = await follow.execute(identity(target), context)
                assert [p.provider_id for p in result.people] == expected
            else:
                with pytest.raises(FollowingFailed, match=failure):
                    await follow.execute(identity(target), context)
        finally:
            event.remove(engine, 'before_cursor_execute', capture)
    # A fresh transaction must never see the speculative fourth membership.
    result = await ListFollowing(following_uows).execute(context)
    assert [p.provider_id for p in result.people] == expected
    assert len(statements) == 3


@pytest.mark.parametrize('existing', [(), (1, 2, 3)])
async def test_missing_person_fails_even_at_cap(following_uows: Factory, existing: tuple[int, ...]) -> None:
    context = await seed(following_uows)
    follow = FollowPerson(following_uows, RecordingFilmographyQueue())
    for i in existing:
        await follow.execute(identity(i), context)
    before = await ListFollowing(following_uows).execute(context)
    with pytest.raises(FollowingFailed, match='missing_person'):
        await follow.execute(identity(999), context)
    assert await ListFollowing(following_uows).execute(context) == before


async def test_following_newest_first_and_repeat_preserves_timestamp(following_uows: Factory) -> None:
    context = await seed(following_uows)
    follow = FollowPerson(following_uows, RecordingFilmographyQueue())
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
    follow = FollowPerson(following_uows, RecordingFilmographyQueue())
    for i in (1, 2):
        await follow.execute(identity(i), context)
    results = await asyncio.wait_for(asyncio.gather(*(follow.execute(identity(i), context) for i in (3, 4)), return_exceptions=True), 3)
    assert len([r for r in results if isinstance(r, FollowingSnapshot)]) == 1
    failures = [r for r in results if isinstance(r, FollowingFailed)]
    assert len(failures) == 1 and failures[0].category == 'follow_limit'
    async with following_uows() as uow:
        assert len(await uow.follows.list_people(context.profile_id)) == 3


async def test_concurrent_repeat_creates_one_row(following_uows: Factory) -> None:
    context = await seed(following_uows)
    follow = FollowPerson(following_uows, RecordingFilmographyQueue())
    results = await asyncio.wait_for(asyncio.gather(*(follow.execute(identity(1), context) for _ in range(2))), 3)
    assert all(len(r.people) == 1 for r in results)
    async with following_uows() as uow:
        assert len(await uow.follows.list_people(context.profile_id)) == 1


async def test_following_uses_current_summary_and_profile_ownership(following_uows: Factory) -> None:
    context = await seed(following_uows)
    await FollowPerson(following_uows, RecordingFilmographyQueue()).execute(identity(1), context)
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
            return await FollowPerson(following_uows, RecordingFilmographyQueue()).execute(identity(1), context)
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
    assert len((await FollowPerson(following_uows, RecordingFilmographyQueue()).execute(identity(1), context)).people) == 1


async def test_rollback_and_cancel_leave_no_membership(following_uows: Factory) -> None:
    context = await seed(following_uows)
    with pytest.raises(RuntimeError):
        async with following_uows() as uow:
            assert await uow.follows.lock_profile(context.profile_id)
            assert await uow.follows.add(context.profile_id, identity(1))
            raise RuntimeError('rollback')
    ready = asyncio.Event()
    async def interrupted() -> None:
        async with following_uows() as uow:
            assert await uow.follows.lock_profile(context.profile_id)
            assert await uow.follows.add(context.profile_id, identity(1))
            ready.set()
            await asyncio.Event().wait()
    task = asyncio.create_task(interrupted())
    await asyncio.wait_for(ready.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, .5)
    assert (await ListFollowing(following_uows).execute(context)).people == ()
    await FollowPerson(following_uows, RecordingFilmographyQueue()).execute(identity(1), context)
    # A fresh engine/connection proves durability independently of the original pool.
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from tests.integration.persistence.conftest import TEST_DATABASE_URL
    engine = create_async_engine(TEST_DATABASE_URL, hide_parameters=True)
    try:
        sessions = async_sessionmaker(engine)
        assert len((await ListFollowing(lambda: PostgresFollowingUnitOfWork(sessions)).execute(context)).people) == 1
    finally:
        await engine.dispose()


async def test_unfollow_survives_fresh_engine(following_uows: Factory) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from tests.integration.persistence.conftest import TEST_DATABASE_URL
    context = await seed(following_uows)
    other = await seed(following_uows)
    for owner, i in ((context, 1), (context, 2), (other, 1)):
        await FollowPerson(following_uows, RecordingFilmographyQueue()).execute(identity(i), owner)
    async with following_uows() as uow:
        before = {(r.profile_id, r.person_id): r.followed_at for r in await uow.session.scalars(select(FollowRow))}
        removed = await uow.session.scalar(select(PersonRow.id).where(PersonRow.tmdb_id == 1))
    for i in (1, 1, 999):
        await UnfollowPerson(following_uows).execute(identity(i), context)
    assert removed is not None
    before.pop((context.profile_id, removed))
    engine = create_async_engine(TEST_DATABASE_URL, hide_parameters=True)
    try:
        sessions = async_sessionmaker(engine)
        async with PostgresFollowingUnitOfWork(sessions) as fresh:
            assert {(r.profile_id, r.person_id): r.followed_at for r in await fresh.session.scalars(select(FollowRow))} == before
    finally:
        await engine.dispose()


async def test_unfollow_rollback_and_cancel_restore_relationship(following_uows: Factory) -> None:
    context = await seed(following_uows)
    await FollowPerson(following_uows, RecordingFilmographyQueue()).execute(identity(1), context)
    ready = asyncio.Event()
    async def interrupted(cancel: bool) -> None:
        async with following_uows() as uow:
            await uow.follows.remove(context.profile_id, identity(1))
            if not cancel:
                raise RuntimeError('rollback')
            ready.set()
            await asyncio.Event().wait()
    with pytest.raises(RuntimeError, match='rollback'):
        await interrupted(False)
    task = asyncio.create_task(interrupted(True))
    await asyncio.wait_for(ready.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, .5)
    assert [p.provider_id for p in (await ListFollowing(following_uows).execute(context)).people] == [1]
    await UnfollowPerson(following_uows).execute(identity(1), context)
    assert (await ListFollowing(following_uows).execute(context)).people == ()



@pytest.mark.parametrize('provider_id', [1, 2, 999])
@pytest.mark.parametrize('missing_profile', [False, True])
async def test_unfollow_uses_one_joined_delete(following_uows: Factory, provider_id: int, missing_profile: bool) -> None:
    context = await seed(following_uows)
    await FollowPerson(following_uows, RecordingFilmographyQueue()).execute(identity(1), context)
    owner = GuestContext(uuid4(), 'absent') if missing_profile else context
    statements: list[str] = []
    def capture(*args: object) -> None:
        statements.append(str(args[2]))
    async with following_uows() as observer:
        connection = await observer.session.connection()
        sync_connection = connection.sync_connection
        assert sync_connection is not None
        engine = sync_connection.engine
        event.listen(engine, 'before_cursor_execute', capture)
        try:
            assert await UnfollowPerson(following_uows).execute(identity(provider_id), owner) is None
        finally:
            event.remove(engine, 'before_cursor_execute', capture)
    assert len(statements) == 1
    assert statements[0].startswith('DELETE FROM follows USING people')
    result = await ListFollowing(following_uows).execute(context)
    assert [p.provider_id for p in result.people] == ([] if not missing_profile and provider_id == 1 else [1])


@pytest.mark.parametrize('delete_first', [True, False])
@pytest.mark.parametrize('same_person', [True, False])
async def test_sequential_follow_and_unfollow_preserve_action_order(following_uows: Factory, delete_first: bool, same_person: bool) -> None:
    context = await seed(following_uows)
    follow = FollowPerson(following_uows, RecordingFilmographyQueue())
    for i in (1, 2, 3):
        await follow.execute(identity(i), context)
    target = identity(1 if same_person else 4)
    if delete_first:
        await UnfollowPerson(following_uows).execute(identity(1), context)
        await follow.execute(target, context)
    else:
        if same_person:
            await follow.execute(target, context)
        else:
            with pytest.raises(FollowingFailed, match='follow_limit'):
                await follow.execute(target, context)
        await UnfollowPerson(following_uows).execute(identity(1), context)
    result = {p.provider_id for p in (await ListFollowing(following_uows).execute(context)).people}
    assert result == ({1, 2, 3} if same_person and delete_first else {2, 3, 4} if delete_first else {2, 3})


async def test_unfollow_does_not_wait_for_profile_lock(following_uows: Factory) -> None:
    context = await seed(following_uows)
    await FollowPerson(following_uows, RecordingFilmographyQueue()).execute(identity(1), context)
    async with following_uows() as blocker:
        assert await blocker.follows.lock_profile(context.profile_id)
        await asyncio.wait_for(UnfollowPerson(following_uows).execute(identity(1), context), 1)
        assert (await ListFollowing(following_uows).execute(context)).people == ()


async def test_unfollow_cannot_remove_an_uncommitted_follow(following_uows: Factory) -> None:
    context = await seed(following_uows)
    entered, release = asyncio.Event(), asyncio.Event()
    class PendingFollow(PostgresFollowingUnitOfWork):
        @override
        async def commit(self) -> None:
            entered.set()
            await release.wait()
            await super().commit()
    pending = asyncio.create_task(FollowPerson(lambda: PendingFollow(following_uows().factory), RecordingFilmographyQueue()).execute(identity(1), context))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        await asyncio.wait_for(UnfollowPerson(following_uows).execute(identity(1), context), 1)
        assert (await ListFollowing(following_uows).execute(context)).people == ()
    finally:
        release.set()
        await asyncio.wait_for(pending, 2)
    assert [p.provider_id for p in (await ListFollowing(following_uows).execute(context)).people] == [1]


async def test_waiting_unfollow_cancel_releases_resources(following_uows: Factory) -> None:
    context = await seed(following_uows)
    await FollowPerson(following_uows, RecordingFilmographyQueue()).execute(identity(1), context)
    started = asyncio.Event()
    class WaitingUnitOfWork(PostgresFollowingUnitOfWork):
        @override
        async def __aenter__(self) -> Self:
            await super().__aenter__()
            started.set()
            return self
    async with following_uows() as blocker:
        # DELETE still waits for a transaction deleting the same membership row.
        await blocker.follows.remove(context.profile_id, identity(1))
        task = asyncio.create_task(UnfollowPerson(lambda: WaitingUnitOfWork(following_uows().factory)).execute(identity(1), context))
        await asyncio.wait_for(started.wait(), 1)
        await asyncio.wait_for(ListFollowing(following_uows).execute(GuestContext(uuid4(), 'other')), .5)
        assert not task.done()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, .5)
    assert len((await ListFollowing(following_uows).execute(context)).people) == 1
    await UnfollowPerson(following_uows).execute(identity(1), context)
