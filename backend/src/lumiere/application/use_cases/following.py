from lumiere.application.ports.following import FollowingUnitOfWorkFactory
from lumiere.domain.access import GuestContext
from lumiere.domain.errors import FollowingFailed
from lumiere.domain.following import FollowingSnapshot, PersonIdentity
from lumiere.domain.people import MAX_PROVIDER_ID, CatalogProvider

GUEST_FOLLOW_LIMIT = 3


class FollowPerson:
    def __init__(self, factory: FollowingUnitOfWorkFactory) -> None:
        self.factory = factory

    async def execute(self, identity: PersonIdentity, context: GuestContext) -> FollowingSnapshot:
        if (identity.provider != CatalogProvider.TMDB
                or type(identity.provider_id) is not int
                or not 1 <= identity.provider_id <= MAX_PROVIDER_ID):
            raise FollowingFailed('invalid_identity')
        async with self.factory() as uow:
            if not await uow.follows.lock_profile(context.profile_id):
                raise FollowingFailed('session')
            person_id = await uow.follows.find_person(identity)
            if person_id is None:
                raise FollowingFailed('missing_person')
            if not await uow.follows.is_following(context.profile_id, person_id):
                if await uow.follows.count(context.profile_id) >= GUEST_FOLLOW_LIMIT:
                    raise FollowingFailed('follow_limit')
                await uow.follows.add(context.profile_id, person_id)
            snapshot = FollowingSnapshot(await uow.follows.list_people(context.profile_id), GUEST_FOLLOW_LIMIT)
            await uow.commit()
            return snapshot


class ListFollowing:
    def __init__(self, factory: FollowingUnitOfWorkFactory) -> None:
        self.factory = factory

    async def execute(self, context: GuestContext) -> FollowingSnapshot:
        async with self.factory() as uow:
            return FollowingSnapshot(await uow.follows.list_people(context.profile_id), GUEST_FOLLOW_LIMIT)


class UnfollowPerson:
    def __init__(self, factory: FollowingUnitOfWorkFactory) -> None:
        self.factory = factory

    async def execute(self, identity: PersonIdentity, context: GuestContext) -> None:
        if (identity.provider != CatalogProvider.TMDB
                or type(identity.provider_id) is not int
                or not 1 <= identity.provider_id <= MAX_PROVIDER_ID):
            raise FollowingFailed('invalid_identity')
        async with self.factory() as uow:
            if not await uow.follows.lock_profile(context.profile_id):
                raise FollowingFailed('session')
            person_id = await uow.follows.find_person(identity)
            if person_id is not None:
                await uow.follows.remove(context.profile_id, person_id)
            await uow.commit()
