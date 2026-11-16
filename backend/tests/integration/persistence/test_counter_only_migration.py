from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, inspect, text

from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork


async def test_counter_only_migration_drops_history_and_preserves_charges(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    revision = ScriptDirectory(str(Path(__file__).parents[3] / "migrations")).get_revision("0004_counter_only_admission")
    assert revision is not None
    migration = revision.module
    limits = '[{"scope":"global","subject":"all","feature":"people_provider","window":"total","cap":100}]'

    def roundtrip(connection: Connection) -> None:
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
            connection.execute(text("INSERT INTO usage_counters (scope, subject, feature, \"window\", count) VALUES ('global','all','people_provider','total',7)"))
            connection.execute(text("INSERT INTO usage_reservations (id, provider_keys, state) VALUES (:id, '[]'::jsonb, 'success')"), {"id": uuid4()})
            migration.upgrade()
            assert not inspect(connection).has_table("usage_reservations")
            assert connection.scalar(text("SELECT count FROM usage_counters")) == 7
            assert connection.scalar(text("SELECT lumiere_admit_and_charge(CAST(:limits AS jsonb))"), {"limits": limits}) is True
            assert connection.scalar(text("SELECT count FROM usage_counters")) == 8
            assert connection.scalar(text("SELECT to_regprocedure('lumiere_admit_and_charge(uuid,jsonb)') IS NULL")) is True
            migration.downgrade()
            assert inspect(connection).has_table("usage_reservations")
            assert connection.scalar(text("SELECT COUNT(*) FROM usage_reservations")) == 0
            assert connection.scalar(text("SELECT count FROM usage_counters")) == 8
            assert connection.scalar(text("SELECT lumiere_admit_and_charge(CAST(:id AS uuid), CAST(:limits AS jsonb))"), {"id": uuid4(), "limits": limits}) is True
            assert connection.scalar(text("SELECT count FROM usage_counters")) == 9
            assert connection.scalar(text("SELECT COUNT(*) FROM usage_reservations WHERE state = 'charged'")) == 1
            migration.upgrade()
            assert not inspect(connection).has_table("usage_reservations")
            assert connection.scalar(text("SELECT count FROM usage_counters")) == 9

    async with uows() as uow:
        await (await uow.session.connection()).run_sync(roundtrip)
