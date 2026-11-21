from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lumiere.adapters.outbound.persistence.models import PersonRow
from lumiere.domain.people import CatalogProvider, PersonSummary


class PostgresPeopleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_batch(self, people: tuple[PersonSummary, ...]) -> None:
        if not people:
            return
        unique: dict[int, PersonSummary] = {}
        for person in people:
            if person.provider != CatalogProvider.TMDB:
                raise ValueError("unsupported provider")
            unique.setdefault(person.provider_id, person)
        statement = insert(PersonRow).values([
            {"tmdb_id": p.provider_id, "name": p.name, "known_for_department": p.known_for_department,
             "known_for": list(p.known_for), "tmdb_profile_path": p.provider_profile_path}
            for _, p in sorted(unique.items())
        ])
        await self.session.execute(statement.on_conflict_do_update(
            index_elements=[PersonRow.tmdb_id],
            set_={field: getattr(statement.excluded, field) for field in
                  ("name", "known_for_department", "known_for", "tmdb_profile_path")},
        ))
