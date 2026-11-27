from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, inspect, text
from sqlalchemy.exc import IntegrityError

from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork


async def test_people_migration_roundtrip(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    scripts = ScriptDirectory(str(Path(__file__).parents[3] / 'migrations'))
    revisions = list(scripts.iterate_revisions('head', '0006_usage_flush_function'))

    def roundtrip(connection: Connection) -> None:
        with Operations.context(MigrationContext.configure(connection)):
            for revision in revisions:
                revision.module.downgrade()
            guest = uuid4()
            connection.execute(text('INSERT INTO guest_profiles(id) VALUES (:id)'), {'id': guest})
            connection.execute(text('INSERT INTO usage_counters VALUES (\'global\',\'all\',\'people_provider\',\'total\',7)'))
            for revision in reversed(revisions):
                revision.module.upgrade()
            for i in range(1, 11):
                identifier = connection.scalar(text("INSERT INTO people(tmdb_id,name,known_for) VALUES (:i,'Tom','[]') RETURNING id"), {'i': i})
                assert 0 <= identifier < 2**40
            try:
                with connection.begin_nested():
                    connection.execute(text("INSERT INTO people(tmdb_id,name,known_for) VALUES (1,'Tom','[]')"))
            except IntegrityError:
                pass
            else:
                raise AssertionError('duplicate TMDB identity accepted')
            for revision in revisions:
                revision.module.downgrade()
            assert not inspect(connection).has_table('people')
            assert connection.scalar(text('SELECT id FROM guest_profiles')) == guest
            assert connection.scalar(text('SELECT count FROM usage_counters')) == 7
            for revision in reversed(revisions):
                revision.module.upgrade()
    async with uows() as uow:
        await (await uow.session.connection()).run_sync(roundtrip)
