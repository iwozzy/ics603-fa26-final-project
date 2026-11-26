import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import event, func, select, text

from lumiere.adapters.outbound.persistence.filmography_unit_of_work import (
    PostgresFilmographyUnitOfWork,
)
from lumiere.adapters.outbound.persistence.models import CreditRow, MovieRow, PersonRow
from lumiere.domain.errors import SearchFailed
from lumiere.domain.filmography import (
    FilmographyCredit,
    FilmographyPerson,
    PersonFilmography,
)
from lumiere.domain.following import PersonIdentity
from lumiere.domain.people import CatalogProvider

type FilmographyUows = Callable[[], PostgresFilmographyUnitOfWork]

PERSON = FilmographyPerson(PersonIdentity(CatalogProvider.TMDB, 401), "Test Person", "Acting")
OTHER_PERSON = FilmographyPerson(PersonIdentity(CatalogProvider.TMDB, 402), "Other Person", None)
CAST = FilmographyCredit(
    provider_credit_id="z-cast",
    movie_provider_id=501,
    person_provider_id=401,
    title="Cast Title",
    overview="Cast overview",
    poster_path="/test.jpg",
    release_date=date(2022, 8, 3),
    credit_type="cast",
    character="Protagonist",
    order=3,
    department=None,
    job=None,
)
CREW = replace(
    CAST,
    provider_credit_id="a-crew",
    title="Crew Title",
    credit_type="crew",
    character=None,
    order=None,
    department="Directing",
    job="Director",
)
PAST_HYDRATION = datetime(2022, 8, 4, tzinfo=UTC)


async def capture_writes(uow: PostgresFilmographyUnitOfWork) -> list[str]:
    statements: list[str] = []

    def capture(conn: object, cursor: object, stmt: str, params: object, context: object, many: bool) -> None:
        sql = stmt.lstrip()
        if sql.upper().startswith(("INSERT", "UPDATE", "DELETE")):
            statements.append(sql)

    connection = await uow.session.connection()
    event.listen(connection.sync_connection, "before_cursor_execute", capture)
    return statements


async def test_cast_and_crew_persist_one_movie_two_credits_in_three_statements(
    filmography_uows: FilmographyUows,
) -> None:
    async with filmography_uows() as uow:
        uow.session.add(PersonRow(
            id=33, tmdb_id=401, name="Prior Name", known_for_department="Production",
            known_for=["Prior Work"], tmdb_profile_path="/prior.jpg",
        ))
        await uow.commit()

    async with filmography_uows() as uow:
        transaction_time = await uow.session.scalar(select(func.now()))
        write_statements = await capture_writes(uow)
        await uow.filmographies.upsert(PersonFilmography(PERSON, (CAST, CREW)))
        async with filmography_uows() as other:
            assert await other.filmographies.last_hydrated(PERSON.identity) is None
            assert (await other.session.scalars(select(MovieRow))).all() == []
            assert (await other.session.scalars(select(CreditRow))).all() == []
        await uow.commit()

    assert len(write_statements) == 3
    assert [sql.split()[:3] for sql in write_statements] == [
        ["INSERT", "INTO", "people"],
        ["INSERT", "INTO", "movies"],
        ["INSERT", "INTO", "credits"],
    ]
    async with filmography_uows() as uow:
        person = (await uow.session.scalars(select(PersonRow))).one()
        movies = (await uow.session.scalars(select(MovieRow))).all()
        credits = (await uow.session.scalars(select(CreditRow))).all()
        assert person.id == 33
        assert person.name == "Test Person" and person.known_for_department == "Acting"
        assert person.known_for == ["Prior Work"] and person.tmdb_profile_path == "/prior.jpg"
        assert transaction_time is not None
        assert await uow.filmographies.last_hydrated(PERSON.identity) == transaction_time
        assert len(movies) == 1 and len(credits) == 2
        assert movies[0].title == "Cast Title"
        assert movies[0].tmdb_id == 501 and movies[0].id != 501
        assert movies[0].overview == "Cast overview"
        assert movies[0].tmdb_poster_path == "/test.jpg"
        assert movies[0].release_date == date(2022, 8, 3)
        assert movies[0].tmdb_last_credits_hydration is None
        assert {c.movie_id for c in credits} == {movies[0].id}
        assert {c.person_id for c in credits} == {33}
        assert len({c.id for c in credits}) == 2
        assert {(c.tmdb_id, c.credit_type, c.credit_character, c.credit_order,
                 c.credit_department, c.credit_job) for c in credits} == {
            ("z-cast", "cast", "Protagonist", 3, None, None),
            ("a-crew", "crew", None, None, "Directing", "Director"),
        }


async def test_conflicts_update_all_mapped_fields_without_removing_older_credits(
    filmography_uows: FilmographyUows,
) -> None:
    writer = replace(CREW, provider_credit_id="writer", department="Writing", job="Writer")
    async with filmography_uows() as uow:
        await uow.filmographies.upsert(PersonFilmography(PERSON, (CAST, CREW, writer, writer)))
        original = (await uow.session.scalars(select(MovieRow))).one()
        moved = (await uow.session.scalars(select(CreditRow).where(CreditRow.tmdb_id == "a-crew"))).one()
        original_id, moved_id = original.id, moved.id
        original.tmdb_last_credits_hydration = PAST_HYDRATION
        await uow.commit()

    renamed = replace(PERSON, name="Renamed Person", known_for_department=None)
    revised = replace(CAST, title="Revised Title", overview=None, poster_path=None,
                      release_date=date(2023, 9, 4), character=None, order=None)
    async with filmography_uows() as uow:
        await uow.filmographies.upsert(PersonFilmography(renamed, (revised,)))
        await uow.commit()

    async with filmography_uows() as uow:
        original = (await uow.session.scalars(select(MovieRow))).one()
        assert original.id == original_id and original.title == "Revised Title"
        assert original.overview is None and original.tmdb_poster_path is None
        assert original.release_date == date(2023, 9, 4)
        assert original.tmdb_last_credits_hydration == PAST_HYDRATION
        person = (await uow.session.scalars(select(PersonRow))).one()
        assert person.name == "Renamed Person" and person.known_for_department is None
        credits = (await uow.session.scalars(select(CreditRow))).all()
        assert {(c.tmdb_id, c.credit_job) for c in credits} == {
            ("z-cast", None), ("a-crew", "Director"), ("writer", "Writer"),
        }
        cast = next(c for c in credits if c.tmdb_id == "z-cast")
        assert cast.credit_character is None and cast.credit_order is None

    reassigned = replace(revised, provider_credit_id="a-crew", movie_provider_id=502,
                         person_provider_id=402, title="Different Movie")
    async with filmography_uows() as uow:
        await uow.filmographies.upsert(PersonFilmography(OTHER_PERSON, (reassigned,)))
        await uow.commit()

    async with filmography_uows() as uow:
        people = {p.tmdb_id: p.id for p in await uow.session.scalars(select(PersonRow))}
        movies = {m.tmdb_id: m.id for m in await uow.session.scalars(select(MovieRow))}
        credits = {c.tmdb_id: c for c in await uow.session.scalars(select(CreditRow))}
        assert set(credits) == {"a-crew", "writer", "z-cast"}
        moved = credits["a-crew"]
        assert moved.id == moved_id and moved.credit_type == "cast"
        assert moved.movie_id == movies[502] and moved.person_id == people[402]
        assert moved.credit_department is None and moved.credit_job is None
        assert credits["writer"].movie_id == original_id
        assert credits["writer"].person_id == people[401]


async def test_empty_filmography_only_inserts_person_and_advances_freshness(
    filmography_uows: FilmographyUows,
) -> None:
    async with filmography_uows() as uow:
        assert await uow.filmographies.last_hydrated(PERSON.identity) is None
        write_statements = await capture_writes(uow)
        await uow.filmographies.upsert(PersonFilmography(PERSON, ()))
        await uow.commit()
    assert [sql.split()[:3] for sql in write_statements] == [["INSERT", "INTO", "people"]]
    async with filmography_uows() as uow:
        person = (await uow.session.scalars(select(PersonRow))).one()
        assert person.name == "Test Person" and person.known_for_department == "Acting"
        assert person.known_for == [] and person.tmdb_profile_path is None
        assert await uow.filmographies.last_hydrated(PERSON.identity) is not None
        assert (await uow.session.scalars(select(MovieRow))).all() == []
        assert (await uow.session.scalars(select(CreditRow))).all() == []


async def test_credit_failure_rolls_back_person_freshness_and_movie_changes(
    filmography_uows: FilmographyUows,
) -> None:
    async with filmography_uows() as uow:
        await uow.filmographies.upsert(PersonFilmography(PERSON, (CAST,)))
        person = (await uow.session.scalars(select(PersonRow))).one()
        person.tmdb_last_movies_hydration = PAST_HYDRATION
        await uow.commit()

    renamed = replace(PERSON, name="Rejected Name")
    changed = replace(CAST, title="Rejected Title")
    invalid = replace(CREW, provider_credit_id=" ", movie_provider_id=502)
    with pytest.raises(SearchFailed, match="storage"):
        async with filmography_uows() as uow:
            write_statements = await capture_writes(uow)
            await uow.filmographies.upsert(PersonFilmography(renamed, (changed, invalid)))
    assert len(write_statements) == 3
    async with filmography_uows() as uow:
        assert await uow.filmographies.last_hydrated(PERSON.identity) == PAST_HYDRATION
        assert (await uow.session.scalars(select(PersonRow.name))).all() == ["Test Person"]
        assert (await uow.session.scalars(select(MovieRow.title))).all() == ["Cast Title"]
        assert (await uow.session.scalars(select(CreditRow.tmdb_id))).all() == ["z-cast"]


async def test_commit_failure_rolls_back_all_three_tables(filmography_uows: FilmographyUows) -> None:
    async with filmography_uows() as uow:
        await uow.session.execute(text("""
            ALTER TABLE credits ADD CONSTRAINT test_unique_job
            UNIQUE (credit_job) DEFERRABLE INITIALLY DEFERRED
        """))
        await uow.commit()

    second_director = replace(CREW, provider_credit_id="other-director")
    with pytest.raises(SearchFailed, match="storage"):
        async with filmography_uows() as uow:
            await uow.filmographies.upsert(PersonFilmography(PERSON, (CREW, second_director)))
            assert (await uow.session.scalars(select(CreditRow))).all()
            await uow.commit()
    async with filmography_uows() as uow:
        assert await uow.filmographies.last_hydrated(PERSON.identity) is None
        assert (await uow.session.scalars(select(PersonRow))).all() == []
        assert (await uow.session.scalars(select(MovieRow))).all() == []
        assert (await uow.session.scalars(select(CreditRow))).all() == []


async def test_overlapping_filmographies_share_movies_with_distinct_credits(
    filmography_uows: FilmographyUows,
) -> None:
    async def write(payload: PersonFilmography) -> None:
        async with filmography_uows() as uow:
            await uow.filmographies.upsert(payload)
            await uow.commit()

    await asyncio.wait_for(asyncio.gather(
        write(PersonFilmography(PERSON, (CAST, replace(CREW, movie_provider_id=502)))),
        write(PersonFilmography(OTHER_PERSON, (
            replace(CAST, provider_credit_id="other-cast", movie_provider_id=502, person_provider_id=402),
            replace(CREW, provider_credit_id="other-crew", person_provider_id=402),
        ))),
    ), 3)
    async with filmography_uows() as uow:
        assert await uow.filmographies.last_hydrated(PERSON.identity) is not None
        assert await uow.filmographies.last_hydrated(OTHER_PERSON.identity) is not None
        linked = await uow.session.execute(select(CreditRow.tmdb_id, MovieRow.tmdb_id, PersonRow.tmdb_id)
            .join(MovieRow, MovieRow.id == CreditRow.movie_id)
            .join(PersonRow, PersonRow.id == CreditRow.person_id))
        assert set(linked) == {
            ("z-cast", 501, 401), ("a-crew", 502, 401),
            ("other-cast", 502, 402), ("other-crew", 501, 402),
        }


async def test_cancelled_filmography_discards_transaction_without_waiting_for_rollback(
    filmography_uows: FilmographyUows, monkeypatch: pytest.MonkeyPatch,
) -> None:
    started, release = asyncio.Event(), asyncio.Event()

    async def write() -> None:
        async with filmography_uows() as uow:
            await uow.filmographies.upsert(PersonFilmography(PERSON, (CAST,)))
            rollback = uow.session.rollback

            async def stalled_rollback() -> None:
                await release.wait()
                await rollback()

            monkeypatch.setattr(uow.session, "rollback", stalled_rollback)
            started.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(write())
    try:
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 0.2)
    finally:
        release.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    async with filmography_uows() as uow:
        assert await uow.filmographies.last_hydrated(PERSON.identity) is None
        assert (await uow.session.scalars(select(PersonRow))).all() == []
        assert (await uow.session.scalars(select(MovieRow))).all() == []
        assert (await uow.session.scalars(select(CreditRow))).all() == []
