from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import Script, ScriptDirectory
from psycopg import IntegrityError as PostgresIntegrityError
from sqlalchemy import BigInteger, Connection, Date, DateTime, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork


def catalog_revision() -> Script:
    scripts = ScriptDirectory(str(Path(__file__).parents[3] / "migrations"))
    assert "0010_movies_credits" in {
        revision.revision for revision in scripts.walk_revisions()
    }
    revision = scripts.get_revision("0010_movies_credits")
    assert revision is not None
    assert revision.down_revision == "0009_people_known_for_default"
    return revision


def assert_catalog_indexes(connection: Connection) -> None:
    schema = inspect(connection)
    movie_indexes = {
        tuple(index["column_names"]): index for index in schema.get_indexes("movies")
    }
    order = movie_indexes[("release_date", "id")]
    assert order["column_sorting"] == {"release_date": ("desc",), "id": ("desc",)}
    credit_indexes = {
        tuple(index["column_names"]) for index in schema.get_indexes("credits")
    }
    assert {("person_id", "movie_id"), ("movie_id", "person_id")} <= credit_indexes


async def test_movies_migration_roundtrip_preserves_existing_data(
    uows: Callable[[], PostgresAccessUnitOfWork],
) -> None:
    revision = catalog_revision()
    from lumiere.adapters.outbound.persistence.models import (
        CreditRow,
        FollowRow,
        MovieRow,
        PersonRow,
    )

    guest = uuid4()
    followed_at = datetime(2026, 10, 3, tzinfo=UTC)
    release_date = date(2026, 8, 20)

    def roundtrip(session: Session) -> None:
        connection = session.connection()
        with Operations.context(MigrationContext.configure(connection)):
            revision.module.downgrade()
            old_tables = set(inspect(connection).get_table_names())
            old_people_columns = {column["name"] for column in inspect(connection).get_columns("people")}
            connection.execute(text("INSERT INTO guest_profiles(id) VALUES (:guest)"), {"guest": guest})
            person_id = connection.scalar(text(
                "INSERT INTO people(tmdb_id, name) VALUES (123, 'Jordan Lee') RETURNING id"
            ))
            connection.execute(
                text("INSERT INTO follows(profile_id, person_id, followed_at) VALUES (:guest, :person, :time)"),
                {"guest": guest, "person": person_id, "time": followed_at},
            )
            connection.execute(text(
                "INSERT INTO usage_counters VALUES ('global', 'all', 'people_provider', 'total', 7)"
            ))

            revision.module.upgrade()
            schema = inspect(connection)
            for table in ("movies", "credits"):
                columns = {column["name"]: column for column in schema.get_columns(table)}
                assert isinstance(columns["id"]["type"], BigInteger)
                assert columns["id"]["identity"]["always"] is True
                assert schema.get_pk_constraint(table)["constrained_columns"] == ["id"]
            date_type = next(column["type"] for column in schema.get_columns("movies") if column["name"] == "release_date")
            assert isinstance(date_type, Date)
            for table, column_name in (
                ("movies", "tmdb_last_credits_hydration"),
                ("people", "tmdb_last_movies_hydration"),
            ):
                column = next(column for column in schema.get_columns(table) if column["name"] == column_name)
                assert column["nullable"]
                stamp_type = column["type"]
                assert isinstance(stamp_type, DateTime) and stamp_type.timezone
            assert_catalog_indexes(connection)

            existing_person = session.scalars(select(PersonRow)).one()
            assert existing_person.id == person_id
            assert existing_person.tmdb_id == 123
            assert existing_person.name == "Jordan Lee"
            assert existing_person.known_for == []
            assert existing_person.tmdb_last_movies_hydration is None
            saved_follow = session.scalars(select(FollowRow)).one()
            assert saved_follow.profile_id == guest
            assert saved_follow.person_id == existing_person.id
            assert saved_follow.followed_at == followed_at
            assert connection.scalar(text("SELECT id FROM guest_profiles")) == guest
            assert connection.scalar(text("SELECT count FROM usage_counters")) == 7

            movie = MovieRow(tmdb_id=456, title="August Evening", release_date=release_date)
            session.add(movie)
            session.flush()
            assert movie.id > 0
            session.add_all([
                CreditRow(tmdb_id="cast-1", movie_id=movie.id, person_id=existing_person.id,
                          credit_type="cast", credit_character="Alex", credit_order=0),
                CreditRow(tmdb_id="crew-1", movie_id=movie.id, person_id=existing_person.id,
                          credit_type="crew", credit_department="Directing", credit_job="Director"),
            ])
            session.flush()
            session.expire_all()
            saved_movie = session.scalars(select(MovieRow)).one()
            assert saved_movie.release_date == release_date
            assert saved_movie.overview is None
            assert saved_movie.tmdb_poster_path is None
            assert saved_movie.tmdb_last_credits_hydration is None
            cast, crew = session.scalars(select(CreditRow).order_by(CreditRow.tmdb_id)).all()
            assert cast.id > 0 and crew.id > 0 and cast.id != crew.id
            assert (cast.credit_character, cast.credit_order, cast.credit_department, cast.credit_job) == (
                "Alex", 0, None, None,
            )
            assert (crew.credit_character, crew.credit_order, crew.credit_department, crew.credit_job) == (
                None, None, "Directing", "Director",
            )

            revision.module.downgrade()
            old_schema = inspect(connection)
            assert set(old_schema.get_table_names()) == old_tables
            assert {column["name"] for column in old_schema.get_columns("people")} == old_people_columns
            assert connection.scalar(text("SELECT id FROM guest_profiles")) == guest
            assert connection.execute(text("SELECT id, tmdb_id, name FROM people")).one() == (
                person_id, 123, "Jordan Lee",
            )
            assert connection.execute(text("SELECT profile_id, person_id, followed_at FROM follows")).one() == (
                guest, person_id, followed_at,
            )
            assert connection.scalar(text("SELECT count FROM usage_counters")) == 7
            revision.module.upgrade()

    async with uows() as uow:
        await uow.session.run_sync(roundtrip)


@pytest.mark.parametrize("blank", ["   ", "\t\n"], ids=["spaces", "tabs-and-newlines"])
async def test_movies_and_credits_enforce_catalog_constraints(
    uows: Callable[[], PostgresAccessUnitOfWork],
    blank: str,
) -> None:
    catalog_revision()

    def verify_constraints(connection: Connection) -> None:
        person_id = connection.scalar(text(
            "INSERT INTO people(tmdb_id, name) VALUES (123, 'Jordan Lee') RETURNING id"
        ))
        movie_insert = "INSERT INTO movies(tmdb_id, title, release_date) VALUES (:provider_id, :title, '2026-08-20')"
        movie_id = connection.scalar(text(movie_insert + " RETURNING id"), {"provider_id": 456, "title": "August Evening"})
        credit_insert = (
            "INSERT INTO credits(tmdb_id, movie_id, person_id, credit_type) "
            "VALUES (:provider_id, :movie, :person, :type)"
        )
        valid_credit = {"provider_id": "cast-1", "movie": movie_id, "person": person_id, "type": "cast"}
        connection.execute(text(credit_insert), valid_credit)
        violations = [
            ("duplicate movie provider ID", movie_insert, {"provider_id": 456, "title": "Other"}, "23505"),
            ("nonpositive movie provider ID", movie_insert, {"provider_id": 0, "title": "Other"}, "23514"),
            ("blank movie title", movie_insert, {"provider_id": 457, "title": blank}, "23514"),
            ("duplicate credit provider ID", credit_insert, valid_credit, "23505"),
            ("blank credit provider ID", credit_insert, {**valid_credit, "provider_id": blank}, "23514"),
            ("invalid credit type", credit_insert, {**valid_credit, "provider_id": "2", "type": "other"}, "23514"),
            ("invalid movie FK", credit_insert, {**valid_credit, "provider_id": "2", "movie": -1}, "23503"),
            ("invalid person FK", credit_insert, {**valid_credit, "provider_id": "2", "person": -1}, "23503"),
            ("referenced movie deletion", "DELETE FROM movies WHERE id = :id", {"id": movie_id}, "23503"),
            ("referenced person deletion", "DELETE FROM people WHERE id = :id", {"id": person_id}, "23503"),
        ]
        for label, statement, parameters, sqlstate in violations:
            with pytest.raises(IntegrityError) as error, connection.begin_nested():
                connection.execute(text(statement), parameters)
            assert isinstance(error.value.orig, PostgresIntegrityError), label
            assert error.value.orig.sqlstate == sqlstate, label

    async with uows() as uow:
        await (await uow.session.connection()).run_sync(verify_constraints)
