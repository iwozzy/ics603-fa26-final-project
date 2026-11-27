from collections.abc import Callable
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError

from lumiere.adapters.outbound.persistence.models import PersonRow
from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork


async def test_omitted_known_for_defaults_to_empty_array(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    async with uows() as uow:
        result = await uow.session.scalar(text("INSERT INTO people(tmdb_id,name) VALUES (1,'Tom') RETURNING known_for"))
        assert result == []


async def test_orm_omitted_known_for_defaults_to_empty_array(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    async with uows() as uow:
        person = PersonRow(tmdb_id=1, name='Tom')
        uow.session.add(person)
        await uow.session.flush()
        assert person.known_for == []


async def test_known_for_default_migration_roundtrip(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    revision = ScriptDirectory(str(Path(__file__).parents[3] / 'migrations')).get_revision('0009_people_known_for_default')
    assert revision is not None

    def roundtrip(connection: Connection) -> None:
        with Operations.context(MigrationContext.configure(connection)):
            revision.module.downgrade()
            connection.execute(text("INSERT INTO people(tmdb_id,name,known_for) VALUES (1,'Tom','[\"Alien\"]')"))
            revision.module.upgrade()
            assert connection.scalar(text('SELECT known_for FROM people WHERE tmdb_id = 1')) == ['Alien']
            assert connection.scalar(text("INSERT INTO people(tmdb_id,name) VALUES (2,'New') RETURNING known_for")) == []
            assert connection.scalar(text("INSERT INTO people(tmdb_id,name,known_for) VALUES (3,'Explicit','[\"Contact\"]') RETURNING known_for")) == ['Contact']
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(text("INSERT INTO people(tmdb_id,name,known_for) VALUES (4,'Null',NULL)"))
            revision.module.downgrade()
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(text("INSERT INTO people(tmdb_id,name) VALUES (5,'Omitted')"))
            assert connection.scalar(text('SELECT known_for FROM people WHERE tmdb_id = 1')) == ['Alien']
            revision.module.upgrade()

    async with uows() as uow:
        await (await uow.session.connection()).run_sync(roundtrip)
