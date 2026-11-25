import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from lumiere.adapters.outbound.persistence.following_unit_of_work import (
    PostgresFollowingUnitOfWork,
)
from lumiere.adapters.outbound.persistence.people_unit_of_work import (
    PostgresPeopleUnitOfWork,
)
from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork

TEST_DATABASE_URL = "postgresql+psycopg://lumiere_test@127.0.0.1:15432/lumiere_test"


def migrate(connection: Connection, target: str) -> None:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[3] / "migrations"))
    config.attributes["connection"] = connection
    if target == "base":
        command.downgrade(config, target)
    else:
        command.upgrade(config, target)


@pytest.fixture
async def uows() -> AsyncIterator[Callable[[], PostgresAccessUnitOfWork]]:
    if os.environ.get("LUMIERE_RUN_PERSISTENCE") != "1":
        pytest.skip("isolated Postgres requires make test-integration")
    # Fixed disposable loopback URL: never consume operator connection settings.
    engine = create_async_engine(TEST_DATABASE_URL, pool_size=5, max_overflow=5, hide_parameters=True)
    async with engine.begin() as connection:
        await connection.run_sync(migrate, "head")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield lambda: PostgresAccessUnitOfWork(factory)
    async with engine.begin() as connection:
        await connection.run_sync(migrate, "base")
    await engine.dispose()


@pytest.fixture
def people_uows(uows: Callable[[], PostgresAccessUnitOfWork]) -> Callable[[], PostgresPeopleUnitOfWork]:
    return lambda: PostgresPeopleUnitOfWork(uows().factory)


@pytest.fixture
def following_uows(uows: Callable[[], PostgresAccessUnitOfWork]) -> Callable[[], PostgresFollowingUnitOfWork]:
    return lambda: PostgresFollowingUnitOfWork(uows().factory)
