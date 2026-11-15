from collections.abc import Callable

import pytest
from sqlalchemy import inspect

from lumiere.adapters.outbound.persistence.models import Base
from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork
from lumiere.domain.access import CounterKey

KEY = CounterKey("global", "all", "people_provider", "total")


async def test_repository_does_not_commit(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    async with uows() as uow:
        await uow.usage.lock_counters((KEY,))
        await uow.usage.add_counts({KEY: 2})
    async with uows() as other:
        assert (await other.usage.lock_counters((KEY,)))[KEY] == 0


async def test_uncommitted_exit_rolls_back(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    async with uows() as uow:
        await uow.usage.lock_counters((KEY,))
        await uow.usage.add_counts({KEY: 1})
        await uow.commit()
    try:
        async with uows() as uow:
            await uow.usage.lock_counters((KEY,))
            await uow.usage.add_counts({KEY: 1})
            raise RuntimeError("synthetic failure")
    except RuntimeError:
        pass
    async with uows() as uow:
        assert (await uow.usage.lock_counters((KEY,)))[KEY] == 1
        # Inspect real schema, including absence of catalog/search persistence.
        tables = await uow.session.run_sync(lambda session: inspect(session.connection()).get_table_names())
        tables = [table for table in tables if table != "alembic_version"]
        assert set(tables) == {"guest_profiles", "guest_sessions", "usage_counters", "usage_reservations"}
        assert set(Base.metadata.tables) == set(tables)


async def test_cancellation_discards_connection_without_waiting_for_network_rollback(uows: Callable[[], PostgresAccessUnitOfWork], monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    started = asyncio.Event()
    release = asyncio.Event()

    async def work() -> None:
        async with uows() as uow:
            await uow.usage.lock_counters((KEY,))
            await uow.usage.add_counts({KEY: 1})
            original = uow.session.rollback

            async def stalled_rollback() -> None:
                await release.wait()
                await original()

            monkeypatch.setattr(uow.session, "rollback", stalled_rollback)
            started.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(work())
    await started.wait()
    task.cancel()
    try:
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 0.2)
    finally:
        release.set()
        await asyncio.sleep(0)
    async with uows() as uow:
        assert (await uow.usage.lock_counters((KEY,)))[KEY] == 0
