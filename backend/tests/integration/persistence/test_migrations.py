from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import Column, Connection, MetaData, String, Table, Uuid, insert, select
from sqlalchemy.dialects.postgresql import JSONB

from lumiere.adapters.outbound.persistence.models import CounterRow
from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork


async def test_atomic_admission_migration_preserves_legacy_charges(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    scripts = ScriptDirectory(str(Path(__file__).parents[3] / "migrations"))
    revision = scripts.get_revision("0002_atomic_admission")
    assert revision is not None
    migration = revision.module
    counter_only = scripts.get_revision("0004_counter_only_admission")
    assert counter_only is not None
    reservations = Table("usage_reservations", MetaData(), Column("id", Uuid(), primary_key=True), Column("provider_keys", JSONB(), nullable=False), Column("state", String(16), nullable=False))
    states = ("reserved", "dispatched", "success", "failed", "cancelled", "released")
    ids = [uuid4() for _ in states]
    charged_id = uuid4()

    def roundtrip(connection: Connection) -> None:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            counter_only.module.downgrade()
            connection.execute(insert(reservations).values(id=charged_id, provider_keys=[], state="charged"))
            migration.downgrade()
            connection.execute(insert(CounterRow).values(scope="global", subject="all", feature="people_provider", window="total", count=17))
            connection.execute(insert(reservations), [{"id": id_, "provider_keys": [], "state": state} for id_, state in zip(ids, states, strict=True)])
            migration.upgrade()

    async with uows() as uow:
        connection = await uow.session.connection()
        await connection.run_sync(roundtrip)
        for id_, state in zip(ids, states, strict=True):
            assert await uow.session.scalar(select(reservations.c.state).where(reservations.c.id == id_)) == state
        assert await uow.session.scalar(select(reservations.c.state).where(reservations.c.id == charged_id)) == "dispatched"
        assert await uow.session.scalar(select(CounterRow.count)) == 17
