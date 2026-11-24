from uuid import UUID

from sqlalchemy import delete, literal, select
from sqlalchemy.dialects.postgresql import insert
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

    async def remove(self, profile_id: UUID, identity: PersonIdentity) -> None:
        await self.session.execute(delete(FollowRow).where(
            FollowRow.profile_id == profile_id,
            FollowRow.person_id == PersonRow.id,
            PersonRow.tmdb_id == identity.provider_id,
        ).execution_options(synchronize_session=False))

    async def add(self, profile_id: UUID, identity: PersonIdentity) -> bool:
        person = select(PersonRow.id).where(PersonRow.tmdb_id == identity.provider_id).cte('person')
        inserted = insert(FollowRow).from_select(
            ['profile_id', 'person_id'], select(literal(profile_id), person.c.id),
        ).on_conflict_do_nothing(index_elements=[FollowRow.profile_id, FollowRow.person_id]).cte('inserted')
        # Select the candidate, not INSERT RETURNING: repeats still have a person.
        return await self.session.scalar(select(person.c.id).add_cte(inserted)) is not None

    async def list_people(self, profile_id: UUID) -> tuple[PersonSummary, ...]:
        rows = await self.session.scalars(select(PersonRow).join(FollowRow, FollowRow.person_id == PersonRow.id).where(FollowRow.profile_id == profile_id).order_by(FollowRow.followed_at.desc(), FollowRow.person_id.desc()))
        return tuple(PersonSummary(provider=CatalogProvider.TMDB, provider_id=row.tmdb_id,
                                   name=row.name, known_for_department=row.known_for_department,
                                   profile_image_url=image_url(row.tmdb_profile_path), known_for=tuple(row.known_for))
                     for row in rows)
