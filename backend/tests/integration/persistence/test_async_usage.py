import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import override
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, event, insert, inspect, select

from lumiere.adapters.outbound.persistence.models import CounterRow
from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork
from lumiere.application.use_cases.search_people import SearchPeople
from lumiere.application.use_cases.usage_admission import UsageAdmissionService
from lumiere.domain.access import CounterKey, GuestContext, UsagePolicy
from lumiere.domain.errors import SearchFailed
from tests.fakes.search import FakeCatalog, FakeClock, FakePeopleQueue

TOTAL = CounterKey("global", "all", "people_provider", "total")
DAY = CounterKey("global", "all", "people_provider", "2026-11-15")


async def test_flush_adds_counts_and_duplicate_commit_does_not_charge_again(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    writer = uuid4()
    async with uows() as uow:
        assert await uow.usage.flush_charges(writer, 1, {TOTAL: 2, DAY: 2}) == {TOTAL: 2, DAY: 2}
        await uow.commit()
    # This retry represents a lost commit acknowledgment, not a new charge.
    async with uows() as uow:
        assert await uow.usage.flush_charges(writer, 1, {TOTAL: 2, DAY: 2}) == {TOTAL: 2, DAY: 2}
        await uow.commit()
    async with uows() as uow:
        assert await uow.usage.flush_charges(writer, 2, {TOTAL: 3, DAY: 3}) == {TOTAL: 5, DAY: 5}
        await uow.commit()
    async with uows() as uow:
        assert await uow.usage.load_counts("2026-11-15") == {TOTAL: 5, DAY: 5}


async def test_flush_rollback_includes_checkpoint(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    writer = uuid4()
    async with uows() as uow:
        await uow.usage.flush_charges(writer, 1, {TOTAL: 7})
    async with uows() as uow:
        assert await uow.usage.load_counts("2026-11-15") == {}
        assert await uow.usage.flush_charges(writer, 1, {TOTAL: 7}) == {TOTAL: 7}
        await uow.commit()


async def test_startup_snapshot_excludes_minute_and_old_daily_rows(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    async with uows() as uow:
        uow.session.add_all([
            CounterRow(scope="global", subject="all", feature=feature, window=window, count=count)
            for feature, window, count in [
                ("people_provider", "total", 12),
                ("people_provider", "2026-11-15", 4),
                ("people_provider", "2026-11-14", 8),
                ("people_request", "2026-11-15T00:00", 4),
                ("guest_bootstrap", "2026-11-15T00:00", 4),
            ]
        ])
        await uow.commit()
    async with uows() as uow:
        assert await uow.usage.load_counts("2026-11-15") == {TOTAL: 12, DAY: 4}


async def test_different_writers_add_without_overwriting_and_return_current_counts(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    async with uows() as uow:
        await uow.usage.flush_charges(uuid4(), 1, {TOTAL: 100})
        await uow.commit()
    async with uows() as uow:
        # Persistence records already dispatched work even above configured caps.
        assert await uow.usage.flush_charges(uuid4(), 1, {TOTAL: 2}) == {TOTAL: 102}
        await uow.commit()


async def test_out_of_sequence_batch_is_rejected(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    writer = uuid4()
    async with uows() as uow:
        with pytest.raises(ValueError):
            await uow.usage.flush_charges(writer, 2, {TOTAL: 1})
    async with uows() as uow:
        assert await uow.session.scalar(select(CounterRow.count)) is None


@pytest.mark.parametrize("key,delta", [(TOTAL, 0), (TOTAL, -1), (CounterKey("ip", "synthetic", "people_request", "2026-11-15T00:00"), 1)])
async def test_flush_refuses_invalid_deltas_and_minute_counters(uows: Callable[[], PostgresAccessUnitOfWork], key: CounterKey, delta: int) -> None:
    async with uows() as uow:
        with pytest.raises(ValueError):
            await uow.usage.flush_charges(uuid4(), 1, {key: delta})


async def test_checkpoint_migration_roundtrip_preserves_counters(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    revision = ScriptDirectory(str(Path(__file__).parents[3] / "migrations")).get_revision("0005_async_usage")
    assert revision is not None

    def roundtrip(connection: Connection) -> None:
        with Operations.context(MigrationContext.configure(connection)):
            connection.execute(insert(CounterRow).values(scope="global", subject="all", feature="people_provider", window="total", count=9))
            revision.module.downgrade()
            assert not inspect(connection).has_table("usage_flush_checkpoints")
            assert connection.scalar(select(CounterRow.count)) == 9
            revision.module.upgrade()
            assert inspect(connection).has_table("usage_flush_checkpoints")
            assert connection.scalar(select(CounterRow.count)) == 9

    async with uows() as uow:
        await (await uow.session.connection()).run_sync(roundtrip)


async def test_concurrent_duplicate_batches_apply_once(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    writer = uuid4()

    async def flush() -> None:
        async with uows() as uow:
            assert await uow.usage.flush_charges(writer, 1, {TOTAL: 3}) == {TOTAL: 3}
            await uow.commit()

    await asyncio.wait_for(asyncio.gather(*(flush() for _ in range(10))), 5)
    async with uows() as uow:
        assert await uow.usage.load_counts("2026-11-15") == {TOTAL: 3}


async def test_search_task_executes_no_sql_and_background_writer_persists_six_counters(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    service = UsageAdmissionService(uows, UsagePolicy(*(100 for _ in range(10))))
    await service.start(FakeClock().now())
    request_task = asyncio.current_task()
    request_calls: list[object] = []

    def observe(*args: object) -> None:
        if asyncio.current_task() is request_task:
            request_calls.append(None)

    async with uows() as probe:
        engine = (await probe.session.connection()).engine.sync_engine
    event.listen(engine, "before_cursor_execute", observe)
    try:
        await SearchPeople(FakeCatalog(), service, FakeClock(), FakePeopleQueue()).execute("Tom", GuestContext(uuid4(), "synthetic-ip"))
        assert request_calls == []
        await asyncio.wait_for(service.drain(), 5)
    finally:
        event.remove(engine, "before_cursor_execute", observe)
        await service.close()
    async with uows() as uow:
        counts = await uow.usage.load_counts("2026-11-15")
        assert len(counts) == 6
        assert set(counts.values()) == {1}
        assert all(key.feature == "people_provider" for key in counts)


async def test_real_commit_with_lost_acknowledgment_retries_without_double_count(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    lose_acknowledgment = True

    class UncertainUow(PostgresAccessUnitOfWork):
        @override
        async def commit(self) -> None:
            nonlocal lose_acknowledgment
            await super().commit()
            if lose_acknowledgment:
                lose_acknowledgment = False
                raise SearchFailed("storage")

    service = UsageAdmissionService(lambda: UncertainUow(uows().factory), UsagePolicy(*(100 for _ in range(10))), retry_delay=0.001)
    await service.start(datetime(2026, 11, 15, tzinfo=UTC))
    try:
        await service.admit_and_charge(GuestContext(uuid4(), "synthetic-ip"), FakeClock().now())
        await asyncio.wait_for(service.drain(), 5)
        async with uows() as uow:
            assert set((await uow.usage.load_counts("2026-11-15")).values()) == {1}
        assert not lose_acknowledgment
    finally:
        await service.close()
