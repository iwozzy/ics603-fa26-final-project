from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, DateTime, inspect, text
from sqlalchemy.exc import IntegrityError

from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork


async def test_follows_migration_constraints_and_roundtrip(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    revision = ScriptDirectory(str(Path(__file__).parents[3] / 'migrations')).get_revision('0008_follows')
    assert revision is not None
    def roundtrip(connection: Connection) -> None:
        with Operations.context(MigrationContext.configure(connection)):
            revision.module.downgrade()
            guest = uuid4()
            connection.execute(text('INSERT INTO guest_profiles VALUES (:id)'), {'id': guest})
            person = connection.scalar(text("INSERT INTO people(tmdb_id,name,known_for) VALUES (1,'Tom','[]') RETURNING id"))
            connection.execute(text("INSERT INTO usage_counters VALUES ('global','all','people_provider','total',7)"))
            revision.module.upgrade()
            schema = inspect(connection)
            assert schema.get_pk_constraint('follows')['constrained_columns'] == ['profile_id', 'person_id']
            assert {fk['referred_table'] for fk in schema.get_foreign_keys('follows')} == {'people', 'guest_profiles'}
            columns = {c['name']: c for c in schema.get_columns('follows')}
            assert all(not c['nullable'] for c in columns.values())
            stamp_type = columns['followed_at']['type']
            assert isinstance(stamp_type, DateTime) and stamp_type.timezone
            assert not schema.has_table('person_follows')
            args = {'guest': guest, 'person': person}
            statement = text('INSERT INTO follows(profile_id,person_id) VALUES (:guest,:person)')
            connection.execute(statement, args)
            for invalid in (args, {'guest': uuid4(), 'person': person}, {'guest': guest, 'person': -1}):
                try:
                    with connection.begin_nested():
                        connection.execute(statement, invalid)
                except IntegrityError:
                    pass
                else:
                    raise AssertionError('invalid follow accepted')
            revision.module.downgrade()
            assert not inspect(connection).has_table('follows')
            assert connection.scalar(text('SELECT id FROM guest_profiles')) == guest
            assert connection.scalar(text('SELECT id FROM people')) == person
            assert connection.scalar(text('SELECT count FROM usage_counters')) == 7
            revision.module.upgrade()
    async with uows() as uow:
        await (await uow.session.connection()).run_sync(roundtrip)
