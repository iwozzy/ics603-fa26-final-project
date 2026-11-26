from datetime import datetime

from sqlalchemy import bindparam, func, select, text
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession

from lumiere.adapters.outbound.persistence.models import PersonRow
from lumiere.domain.filmography import FilmographyCredit, PersonFilmography
from lumiere.domain.following import PersonIdentity
from lumiere.domain.people import CatalogProvider

_UPSERT_MOVIES = text("""
    INSERT INTO movies (tmdb_id, title, overview, tmdb_poster_path, release_date)
    SELECT batch.tmdb_id, batch.title, batch.overview, batch.tmdb_poster_path, batch.release_date
    FROM jsonb_to_recordset(:movies) AS batch (
        tmdb_id bigint, title text, overview text, tmdb_poster_path text, release_date date
    )
    ORDER BY batch.tmdb_id
    ON CONFLICT (tmdb_id) DO UPDATE SET
        title = EXCLUDED.title,
        overview = EXCLUDED.overview,
        tmdb_poster_path = EXCLUDED.tmdb_poster_path,
        release_date = EXCLUDED.release_date
""").bindparams(bindparam("movies", type_=JSONB))

_UPSERT_CREDITS = text("""
    INSERT INTO credits (
        tmdb_id, movie_id, person_id, credit_type, credit_character, credit_order,
        credit_department, credit_job
    )
    SELECT batch.tmdb_id, movies.id, people.id, batch.credit_type, batch.credit_character,
           batch.credit_order, batch.credit_department, batch.credit_job
    FROM jsonb_to_recordset(:credits) AS batch (
        tmdb_id text, movie_tmdb_id bigint, person_tmdb_id bigint, credit_type text,
        credit_character text, credit_order integer, credit_department text, credit_job text
    )
    JOIN movies ON movies.tmdb_id = batch.movie_tmdb_id
    JOIN people ON people.tmdb_id = batch.person_tmdb_id
    ORDER BY batch.tmdb_id
    ON CONFLICT (tmdb_id) DO UPDATE SET
        movie_id = EXCLUDED.movie_id,
        person_id = EXCLUDED.person_id,
        credit_type = EXCLUDED.credit_type,
        credit_character = EXCLUDED.credit_character,
        credit_order = EXCLUDED.credit_order,
        credit_department = EXCLUDED.credit_department,
        credit_job = EXCLUDED.credit_job
""").bindparams(bindparam("credits", type_=JSONB))


class PostgresFilmographyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def last_hydrated(self, identity: PersonIdentity) -> datetime | None:
        if identity.provider != CatalogProvider.TMDB:
            raise ValueError("unsupported provider")
        return await self.session.scalar(
            select(PersonRow.tmdb_last_movies_hydration).where(PersonRow.tmdb_id == identity.provider_id)
        )

    async def upsert(self, payload: PersonFilmography) -> None:
        person = payload.person
        if person.identity.provider != CatalogProvider.TMDB:
            raise ValueError("unsupported provider")
        statement = insert(PersonRow).inline().values(
            tmdb_id=person.identity.provider_id,
            name=person.name,
            known_for_department=person.known_for_department,
            tmdb_last_movies_hydration=func.now(),
        )
        await self.session.execute(statement.on_conflict_do_update(
            index_elements=[PersonRow.tmdb_id],
            set_={
                "name": statement.excluded.name,
                "known_for_department": statement.excluded.known_for_department,
                "tmdb_last_movies_hydration": statement.excluded.tmdb_last_movies_hydration,
            },
        ))
        if not payload.credits:
            return

        movies: dict[int, FilmographyCredit] = {}
        credits: dict[str, FilmographyCredit] = {}
        for credit in payload.credits:
            # Provider order chooses movie summaries before SQL sorts the writes.
            movies.setdefault(credit.movie_provider_id, credit)
            credits.setdefault(credit.provider_credit_id, credit)

        await self.session.execute(_UPSERT_MOVIES, {"movies": [
            {
                "tmdb_id": movie.movie_provider_id,
                "title": movie.title,
                "overview": movie.overview,
                "tmdb_poster_path": movie.poster_path,
                "release_date": movie.release_date.isoformat(),
            }
            for movie in movies.values()
        ]})
        await self.session.execute(_UPSERT_CREDITS, {"credits": [
            {
                "tmdb_id": credit.provider_credit_id,
                "movie_tmdb_id": credit.movie_provider_id,
                "person_tmdb_id": credit.person_provider_id,
                "credit_type": credit.credit_type,
                "credit_character": credit.character,
                "credit_order": credit.order,
                "credit_department": credit.department,
                "credit_job": credit.job,
            }
            for credit in credits.values()
        ]})
