from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumiere.adapters.outbound.clients.tmdb_people.mapper import image_url
from lumiere.adapters.outbound.persistence.models import (
    FollowRow,
    GuestProfileRow,
    PersonRow,
)
from lumiere.domain.following import PersonIdentity
from lumiere.domain.people import CatalogProvider, PersonSummary


class PostgresFollowingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_profile(self, profile_id: UUID) -> bool:
        return await self.session.scalar(select(GuestProfileRow.id).where(GuestProfileRow.id == profile_id).with_for_update()) is not None

    async def find_person(self, identity: PersonIdentity) -> int | None:
        return await self.session.scalar(select(PersonRow.id).where(PersonRow.tmdb_id == identity.provider_id))

    async def is_following(self, profile_id: UUID, person_id: int) -> bool:
        return await self.session.scalar(select(FollowRow.person_id).where(FollowRow.profile_id == profile_id, FollowRow.person_id == person_id)) is not None

    async def count(self, profile_id: UUID) -> int:
        return (await self.session.scalar(select(func.count()).select_from(FollowRow).where(FollowRow.profile_id == profile_id))) or 0

    async def add(self, profile_id: UUID, person_id: int) -> None:
        self.session.add(FollowRow(profile_id=profile_id, person_id=person_id))
        await self.session.flush()

    async def list_people(self, profile_id: UUID) -> tuple[PersonSummary, ...]:
        rows = await self.session.scalars(select(PersonRow).join(FollowRow, FollowRow.person_id == PersonRow.id).where(FollowRow.profile_id == profile_id).order_by(FollowRow.followed_at.desc(), FollowRow.person_id.desc()))
        return tuple(PersonSummary(provider=CatalogProvider.TMDB, provider_id=row.tmdb_id,
                                   name=row.name, known_for_department=row.known_for_department,
                                   profile_image_url=image_url(row.tmdb_profile_path), known_for=tuple(row.known_for))
                     for row in rows)
