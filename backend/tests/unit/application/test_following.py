from typing import cast
from uuid import uuid4

import pytest

from lumiere.application.use_cases.following import FollowPerson, ListFollowing
from lumiere.domain.access import GuestContext
from lumiere.domain.errors import FollowingFailed
from lumiere.domain.following import PersonIdentity
from lumiere.domain.people import CatalogProvider
from tests.fakes.following import MemoryFollowing
from tests.fakes.search import sample_person


@pytest.fixture
def context() -> GuestContext:
    return GuestContext(uuid4(), 'synthetic-ip')


@pytest.fixture
def store(context: GuestContext) -> MemoryFollowing:
    store = MemoryFollowing()
    store.profiles.add(context.profile_id)
    for i in (4139, 2, 3, 4):
        store.people[i] = sample_person(i)
    return store


def identity(provider_id: int = 4139) -> PersonIdentity:
    return PersonIdentity(CatalogProvider.TMDB, provider_id)


async def test_follow_records_matching_person_before_success(store: MemoryFollowing, context: GuestContext) -> None:
    result = await FollowPerson(store).execute(identity(), context)
    assert result.limit == 3
    assert [p.provider_id for p in result.people] == [4139]
    assert store.commits == 1
    assert store.operations.index('lock_profile') < store.operations.index('count')
    assert store.operations.index('list_people') < store.operations.index('commit')


async def test_missing_person_rolls_back(store: MemoryFollowing, context: GuestContext) -> None:
    with pytest.raises(FollowingFailed, match='missing_person'):
        await FollowPerson(store).execute(identity(999), context)
    assert not store.memberships
    assert store.rollbacks == 1
    assert store.commits == 0


async def test_missing_profile_is_rejected(store: MemoryFollowing) -> None:
    with pytest.raises(FollowingFailed, match='session'):
        await FollowPerson(store).execute(identity(), GuestContext(uuid4(), 'other'))
    assert store.operations == ['enter', 'lock_profile', 'rollback']


async def test_existing_follow_succeeds_at_three_without_insert(store: MemoryFollowing, context: GuestContext) -> None:
    follow = FollowPerson(store)
    for i in (4139, 2, 3):
        await follow.execute(identity(i), context)
    before = dict(store.memberships)
    store.operations.clear()
    result = await follow.execute(identity(), context)
    assert store.memberships == before
    assert [p.provider_id for p in result.people] == [3, 2, 4139]
    assert 'add' not in store.operations
    assert 'count' not in store.operations


async def test_fourth_distinct_follow_is_rejected(store: MemoryFollowing, context: GuestContext) -> None:
    follow = FollowPerson(store)
    for i in (4139, 2, 3):
        await follow.execute(identity(i), context)
    with pytest.raises(FollowingFailed, match='follow_limit'):
        await follow.execute(identity(4), context)
    assert len(store.memberships) == 3
    assert store.commits == 3


@pytest.mark.parametrize('raw', [True, '4139', 1.5, 0, -1, 2**53])
async def test_invalid_identity_has_no_storage_work(store: MemoryFollowing, context: GuestContext, raw: object) -> None:
    with pytest.raises(FollowingFailed, match='invalid_identity'):
        await FollowPerson(store).execute(PersonIdentity(CatalogProvider.TMDB, cast(int, raw)), context)
    assert not store.operations


async def test_unsupported_provider_has_no_storage_work(store: MemoryFollowing, context: GuestContext) -> None:
    with pytest.raises(FollowingFailed, match='invalid_identity'):
        await FollowPerson(store).execute(PersonIdentity(cast(CatalogProvider, 'other'), 4139), context)
    assert not store.operations


async def test_list_is_owned_by_requesting_profile(store: MemoryFollowing, context: GuestContext) -> None:
    await FollowPerson(store).execute(identity(), context)
    other = GuestContext(uuid4(), 'other')
    store.profiles.add(other.profile_id)
    store.operations.clear()
    result = await ListFollowing(store).execute(other)
    assert result.people == ()
    assert result.limit == 3
    assert store.operations == ['enter', 'list_people', 'rollback']


async def test_commit_failure_never_persists_membership(store: MemoryFollowing, context: GuestContext) -> None:
    store.commit_error = RuntimeError('storage')
    with pytest.raises(RuntimeError, match='storage'):
        await FollowPerson(store).execute(identity(), context)
    assert store.memberships == {}
    assert store.rollbacks == 1
    assert store.commits == 0
