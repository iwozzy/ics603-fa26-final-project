import os
from collections.abc import AsyncIterator, Callable

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from lumiere.adapters.outbound.persistence.models import Base
from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork

TEST_DATABASE_URL = "postgresql+psycopg://lumiere_test@127.0.0.1:15432/lumiere_test"


@pytest.fixture
async def uows() -> AsyncIterator[Callable[[], PostgresAccessUnitOfWork]]:
    if os.environ.get("LUMIERE_RUN_PERSISTENCE") != "1":
        pytest.skip("isolated Postgres requires make test-integration")
    # Fixed disposable loopback URL: never consume operator connection settings.
    engine = create_async_engine(TEST_DATABASE_URL, pool_size=5, max_overflow=5, hide_parameters=True)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield lambda: PostgresAccessUnitOfWork(factory)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()
