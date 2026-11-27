import asyncio
from typing import cast, override
from uuid import UUID, uuid4

import pytest

from lumiere.application.use_cases.following import (
    FollowPerson,
    ListFollowing,
    UnfollowPerson,
)
from lumiere.domain.access import GuestContext
from lumiere.domain.errors import FollowingFailed
from lumiere.domain.following import PersonIdentity
from lumiere.domain.people import CatalogProvider
from tests.fakes.following import MemoryFollowing, MemoryFollowingTransaction
from tests.fakes.hydration import RecordingFilmographyQueue
from tests.fakes.search import sample_person


@pytest.fixture
def context() -> GuestContext:
    return GuestContext(uuid4(), 'synthetic-ip')


@pytest.fixture
def queue() -> RecordingFilmographyQueue:
    return RecordingFilmographyQueue()


@pytest.fixture
def store(context: GuestContext) -> MemoryFollowing:
    store = MemoryFollowing()
    store.profiles.add(context.profile_id)
    for i in (4139, 2, 3, 4):
        store.people[i] = sample_person(i)
    return store


def identity(provider_id: int = 4139) -> PersonIdentity:
    return PersonIdentity(CatalogProvider.TMDB, provider_id)


async def test_follow_records_matching_person_before_success(store: MemoryFollowing, context: GuestContext, queue: RecordingFilmographyQueue) -> None:
    result = await FollowPerson(store, queue).execute(identity(), context)
    assert result.limit == 3
    assert [p.provider_id for p in result.people] == [4139]
    assert store.commits == 1
    assert store.operations.index('lock_profile') < store.operations.index('add')
    assert store.operations.index('list_people') < store.operations.index('commit')


async def test_missing_person_rolls_back(store: MemoryFollowing, context: GuestContext, queue: RecordingFilmographyQueue) -> None:
    with pytest.raises(FollowingFailed, match='missing_person'):
        await FollowPerson(store, queue).execute(identity(999), context)
    assert not store.memberships
    assert store.rollbacks == 1
    assert store.commits == 0
    assert queue.enqueued == [(identity(999), context)]


async def test_missing_profile_is_rejected(store: MemoryFollowing, queue: RecordingFilmographyQueue) -> None:
    missing_guest = GuestContext(uuid4(), 'other')
    with pytest.raises(FollowingFailed, match='session'):
        await FollowPerson(store, queue).execute(identity(), missing_guest)
    assert queue.enqueued == [(identity(), missing_guest)]
    assert store.operations == ['enter', 'lock_profile', 'rollback']


async def test_existing_follow_succeeds_at_three_without_changing_timestamp(store: MemoryFollowing, context: GuestContext, queue: RecordingFilmographyQueue) -> None:
    follow = FollowPerson(store, queue)
    for i in (4139, 2, 3):
        await follow.execute(identity(i), context)
    before = dict(store.memberships)
    store.operations.clear()
    result = await follow.execute(identity(), context)
    assert store.memberships == before
    assert [p.provider_id for p in result.people] == [3, 2, 4139]
    assert store.operations == ['enter', 'lock_profile', 'add', 'list_people', 'commit']
    assert queue.enqueued == [(identity(i), context) for i in (4139, 2, 3, 4139)]


async def test_fourth_distinct_follow_is_rejected(store: MemoryFollowing, context: GuestContext, queue: RecordingFilmographyQueue) -> None:
    follow = FollowPerson(store, queue)
    for i in (4139, 2, 3):
        await follow.execute(identity(i), context)
    before = dict(store.memberships)
    store.operations.clear()
    with pytest.raises(FollowingFailed, match='follow_limit'):
        await follow.execute(identity(4), context)
    assert store.memberships == before
    assert store.commits == 3
    assert store.operations == ['enter', 'lock_profile', 'add', 'list_people', 'rollback']
    assert queue.enqueued == [(identity(i), context) for i in (4139, 2, 3, 4)]


@pytest.mark.parametrize('use_case', [FollowPerson, UnfollowPerson])
@pytest.mark.parametrize('raw', [True, '4139', 1.5, 0, -1, 2**53])
async def test_invalid_identity_has_no_storage_work(store: MemoryFollowing, context: GuestContext, raw: object, use_case: type[FollowPerson] | type[UnfollowPerson], queue: RecordingFilmographyQueue) -> None:
    with pytest.raises(FollowingFailed, match='invalid_identity'):
        await (FollowPerson(store, queue) if use_case is FollowPerson else UnfollowPerson(store)).execute(PersonIdentity(CatalogProvider.TMDB, cast(int, raw)), context)
    assert not store.operations and not queue.enqueued


@pytest.mark.parametrize('use_case', [FollowPerson, UnfollowPerson])
async def test_unsupported_provider_has_no_storage_work(store: MemoryFollowing, context: GuestContext, use_case: type[FollowPerson] | type[UnfollowPerson], queue: RecordingFilmographyQueue) -> None:
    with pytest.raises(FollowingFailed, match='invalid_identity'):
        await (FollowPerson(store, queue) if use_case is FollowPerson else UnfollowPerson(store)).execute(PersonIdentity(cast(CatalogProvider, 'other'), 4139), context)
    assert not store.operations and not queue.enqueued


async def test_list_is_owned_by_requesting_profile(store: MemoryFollowing, context: GuestContext, queue: RecordingFilmographyQueue) -> None:
    await FollowPerson(store, queue).execute(identity(), context)
    other = GuestContext(uuid4(), 'other')
    store.profiles.add(other.profile_id)
    store.operations.clear()
    result = await ListFollowing(store).execute(other)
    assert result.people == ()
    assert result.limit == 3
    assert store.operations == ['enter', 'list_people', 'rollback']


async def test_commit_failure_never_persists_membership(store: MemoryFollowing, context: GuestContext, queue: RecordingFilmographyQueue) -> None:
    store.commit_error = RuntimeError('storage')
    with pytest.raises(RuntimeError, match='storage'):
        await FollowPerson(store, queue).execute(identity(), context)
    assert store.memberships == {}
    assert store.rollbacks == 1
    assert store.commits == 0
    assert queue.enqueued == [(identity(), context)]


async def test_unfollow_commits_only_owned_relationship(store: MemoryFollowing, context: GuestContext, queue: RecordingFilmographyQueue) -> None:
    other = GuestContext(uuid4(), 'other')
    store.profiles.add(other.profile_id)
    for owner, i in ((context, 4139), (context, 2), (other, 4139)):
        await FollowPerson(store, queue).execute(identity(i), owner)
    before = dict(store.memberships)
    enqueued = list(queue.enqueued)
    store.operations.clear()
    assert await UnfollowPerson(store).execute(identity(), context) is None
    before.pop((context.profile_id, 4139))
    assert store.memberships == before
    assert store.operations == ['enter', 'remove', 'commit']
    assert queue.enqueued == enqueued


async def test_unfollow_absent_relationship_and_person_are_idempotent(store: MemoryFollowing, context: GuestContext) -> None:
    for i in (4139, 4139, 999):
        assert await UnfollowPerson(store).execute(identity(i), context) is None
    assert store.memberships == {}
    assert store.commits == 3
    assert store.operations == ['enter', 'remove', 'commit'] * 3


async def test_unfollow_missing_profile_is_a_committed_no_op(store: MemoryFollowing) -> None:
    assert await UnfollowPerson(store).execute(identity(), GuestContext(uuid4(), 'other')) is None
    assert store.memberships == {}
    assert store.operations == ['enter', 'remove', 'commit']
    assert store.commits == 1


async def test_unfollow_commit_failure_preserves_membership(store: MemoryFollowing, context: GuestContext, queue: RecordingFilmographyQueue) -> None:
    await FollowPerson(store, queue).execute(identity(), context)
    before = dict(store.memberships)
    store.commit_error = RuntimeError('storage')
    with pytest.raises(RuntimeError, match='storage'):
        await UnfollowPerson(store).execute(identity(), context)
    assert store.memberships == before
    assert store.rollbacks == 1


async def test_hydration_is_enqueued_before_following_storage_can_block(
    store: MemoryFollowing, context: GuestContext, queue: RecordingFilmographyQueue,
) -> None:
    entered, release = asyncio.Event(), asyncio.Event()

    class BlockedFollowing(MemoryFollowingTransaction):
        @override
        async def lock_profile(self, profile_id: UUID) -> bool:
            entered.set()
            await release.wait()
            return await super().lock_profile(profile_id)

    following = FollowPerson(lambda: BlockedFollowing(store), queue)
    task = asyncio.create_task(following.execute(identity(), context))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        assert queue.enqueued == [(identity(), context)]
        assert not task.done() and not store.memberships
    finally:
        release.set()
        await task


async def test_enqueue_failure_does_not_fail_follow(
    store: MemoryFollowing, context: GuestContext, queue: RecordingFilmographyQueue,
) -> None:
    queue.error = RuntimeError('synthetic queue error')
    snapshot = await FollowPerson(store, queue).execute(identity(), context)
    assert [person.provider_id for person in snapshot.people] == [4139]
    assert store.commits == 1


async def test_enqueue_failure_does_not_mask_a_following_failure(
    store: MemoryFollowing, context: GuestContext, queue: RecordingFilmographyQueue,
) -> None:
    queue.error = RuntimeError('synthetic queue error')
    with pytest.raises(FollowingFailed, match='missing_person'):
        await FollowPerson(store, queue).execute(identity(999), context)
    assert not store.commits
