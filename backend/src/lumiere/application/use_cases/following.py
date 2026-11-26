from lumiere.application.ports.filmography import FilmographyQueue
from lumiere.application.ports.following import FollowingUnitOfWorkFactory
from lumiere.domain.access import GuestContext
from lumiere.domain.errors import FollowingFailed
from lumiere.domain.following import FollowingSnapshot, PersonIdentity
from lumiere.domain.people import MAX_PROVIDER_ID, CatalogProvider

GUEST_FOLLOW_LIMIT = 3


class FollowPerson:
    def __init__(self, factory: FollowingUnitOfWorkFactory, hydration: FilmographyQueue) -> None:
        self.factory = factory
        self.hydration = hydration

    async def execute(self, identity: PersonIdentity, context: GuestContext) -> FollowingSnapshot:
        if (identity.provider != CatalogProvider.TMDB
                or type(identity.provider_id) is not int
                or not 1 <= identity.provider_id <= MAX_PROVIDER_ID):
            raise FollowingFailed('invalid_identity')
        try:
            self.hydration.enqueue(identity, context)
        except Exception:  # noqa: BLE001, S110 — hydration is independent of following
            pass
        async with self.factory() as uow:
            if not await uow.follows.lock_profile(context.profile_id):
                raise FollowingFailed('session')
            if not await uow.follows.add(context.profile_id, identity):
                raise FollowingFailed('missing_person')
            snapshot = FollowingSnapshot(await uow.follows.list_people(context.profile_id), GUEST_FOLLOW_LIMIT)
            if len(snapshot.people) > GUEST_FOLLOW_LIMIT:
                raise FollowingFailed('follow_limit')
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
            await uow.follows.remove(context.profile_id, identity)
            await uow.commit()
