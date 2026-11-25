import asyncio
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, event, insert, select, text

from lumiere.adapters.outbound.persistence.models import (
    CounterRow,
    UsageFlushCheckpointRow,
)
from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork
from lumiere.domain.access import CounterKey

TOTAL = CounterKey("global", "all", "people_provider", "total")
DAY = CounterKey("global", "all", "people_provider", "2026-11-18")


@pytest.mark.parametrize("duplicate", [False, True])
async def test_flush_uses_one_statement_including_commit(uows: Callable[[], PostgresAccessUnitOfWork], duplicate: bool) -> None:
    writer = uuid4()
    if duplicate:
        async with uows() as uow:
            await uow.usage.flush_charges(writer, 1, {TOTAL: 2, DAY: 3})
            await uow.commit()

    async with uows() as uow:
        connection = await uow.session.connection()
        calls: list[object] = []

        def observe(*args: object) -> None:
            calls.append(None)

        event.listen(connection.sync_connection, "before_cursor_execute", observe)
        try:
            assert await uow.usage.flush_charges(writer, 1, {TOTAL: 2, DAY: 3}) == {TOTAL: 2, DAY: 3}
            await uow.commit()
            assert len(calls) == 1
        finally:
            event.remove(connection.sync_connection, "before_cursor_execute", observe)


async def test_flush_accepts_bigint_sequence(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    writer = uuid4()
    async with uows() as uow:
        await uow.session.execute(insert(UsageFlushCheckpointRow).values(writer_id=writer, sequence=2**31))
        await uow.commit()
    async with uows() as uow:
        assert await uow.usage.flush_charges(writer, 2**31 + 1, {TOTAL: 4}) == {TOTAL: 4}
        await uow.commit()
    async with uows() as uow:
        assert await uow.usage.flush_charges(writer, 2**31 + 1, {TOTAL: 4}) == {TOTAL: 4}


@pytest.mark.parametrize("duplicate", [False, True])
async def test_flush_refreshes_retained_counter(uows: Callable[[], PostgresAccessUnitOfWork], duplicate: bool) -> None:
    writer = uuid4()
    async with uows() as uow:
        await uow.usage.flush_charges(writer, 1, {TOTAL: 2})
        await uow.commit()
    async with uows() as uow:
        retained = await uow.session.scalar(select(CounterRow))
        assert retained is not None and retained.count == 2
        if duplicate:
            async with uows() as other:
                await other.usage.flush_charges(uuid4(), 1, {TOTAL: 3})
                await other.commit()
        assert await uow.usage.flush_charges(writer, 1 if duplicate else 2, {TOTAL: 3}) == {TOTAL: 5}
        assert retained.count == 5
        await uow.commit()


@pytest.mark.parametrize("invalid_sequence", [3, 2**63])
async def test_rejected_sequence_keeps_prior_batch_in_transaction(uows: Callable[[], PostgresAccessUnitOfWork], invalid_sequence: int) -> None:
    writer = uuid4()
    async with uows() as uow:
        await uow.usage.flush_charges(writer, 1, {TOTAL: 3})
        with pytest.raises(ValueError, match="usage batch out of sequence"):
            await uow.usage.flush_charges(writer, invalid_sequence, {TOTAL: 9})
        await uow.commit()
    async with uows() as uow:
        assert await uow.usage.load_counts("2026-11-18") == {TOTAL: 3}
        assert await uow.session.scalar(select(UsageFlushCheckpointRow.sequence)) == 1


async def test_flush_rejects_older_batch_without_changing_counts(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    writer = uuid4()
    for sequence in (1, 2):
        async with uows() as uow:
            await uow.usage.flush_charges(writer, sequence, {TOTAL: 3})
            await uow.commit()
    with pytest.raises(ValueError, match="usage batch out of sequence"):
        async with uows() as uow:
            await uow.usage.flush_charges(writer, 1, {TOTAL: 3})
    async with uows() as uow:
        assert await uow.session.scalar(select(CounterRow.count)) == 6
        assert await uow.session.scalar(select(UsageFlushCheckpointRow.sequence)) == 2


async def test_concurrent_writers_add_overlapping_counters(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    async def flush(reverse: bool) -> None:
        deltas = {DAY: 3, TOTAL: 2} if reverse else {TOTAL: 2, DAY: 3}
        async with uows() as uow:
            await uow.usage.flush_charges(uuid4(), 1, deltas)
            await uow.commit()

    await asyncio.wait_for(asyncio.gather(*(flush(i % 2 == 0) for i in range(10))), 5)
    async with uows() as uow:
        assert await uow.usage.load_counts("2026-11-18") == {TOTAL: 20, DAY: 30}


async def test_function_migration_roundtrip_preserves_counts_and_checkpoint(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    revision = ScriptDirectory(str(Path(__file__).parents[3] / "migrations")).get_revision("0006_usage_flush_function")
    assert revision is not None
    writer = uuid4()
    async with uows() as uow:
        await uow.usage.flush_charges(writer, 1, {TOTAL: 7})
        await uow.commit()

    def roundtrip(connection: Connection) -> None:
        with Operations.context(MigrationContext.configure(connection)):
            revision.module.downgrade()
            assert connection.scalar(text("SELECT to_regprocedure('lumiere_flush_charges(uuid,bigint,jsonb)')")) is None
            assert connection.scalar(select(CounterRow.count)) == 7
            assert connection.scalar(select(UsageFlushCheckpointRow.sequence)) == 1
            revision.module.upgrade()
            assert connection.scalar(text("SELECT to_regprocedure('lumiere_flush_charges(uuid,bigint,jsonb)')")) is not None

    async with uows() as uow:
        await (await uow.session.connection()).run_sync(roundtrip)
        assert await uow.usage.flush_charges(writer, 1, {TOTAL: 7}) == {TOTAL: 7}
        await uow.commit()
