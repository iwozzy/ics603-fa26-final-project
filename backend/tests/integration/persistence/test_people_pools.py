import asyncio
from collections.abc import Callable
from contextlib import AsyncExitStack

import pytest
from sqlalchemy import text

from lumiere.adapters.outbound.persistence.pools import PoolRegistry
from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork
from tests.integration.persistence.conftest import TEST_DATABASE_URL


async def test_people_pool_is_independent_and_bounded(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    registry = PoolRegistry()
    application = registry.register('application', TEST_DATABASE_URL)
    people = registry.register('people_writer', TEST_DATABASE_URL)
    try:
        async with AsyncExitStack() as stack:
            for _ in range(10):
                await stack.enter_async_context(application.engine.connect())
            async with people.engine.connect() as first, people.engine.connect() as second:
                pids = await asyncio.gather(first.scalar(text('SELECT pg_backend_pid()')), second.scalar(text('SELECT pg_backend_pid()')))
                assert pids[0] != pids[1]
            connections = [await stack.enter_async_context(people.engine.connect()) for _ in range(10)]
            entered = asyncio.Event()
            async def eleventh() -> None:
                async with people.engine.connect() as connection:
                    await connection.execute(text('SELECT 1'))
                    entered.set()
            task = asyncio.create_task(eleventh())
            try:
                with pytest.raises(TimeoutError):
                    await asyncio.wait_for(entered.wait(), .03)
                await connections[0].close()
                await asyncio.wait_for(task, 1)
                assert entered.is_set()
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    finally:
        await registry.close()
