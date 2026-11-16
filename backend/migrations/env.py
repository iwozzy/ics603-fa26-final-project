import asyncio
import os

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from lumiere.adapters.outbound.persistence.models import Base


def apply(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run() -> None:
    url = os.environ["LUMIERE_MIGRATION_DATABASE_URL"]
    if not url.startswith("postgresql+psycopg://"):
        raise RuntimeError("a direct Postgres migration connection is required")
    engine = create_async_engine(url, poolclass=NullPool, hide_parameters=True)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(apply)
    finally:
        await engine.dispose()


connection = context.config.attributes.get("connection")
if connection is not None:
    apply(connection)
else:
    asyncio.run(run())
