from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_sessions(url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(url, pool_size=5, max_overflow=5, pool_pre_ping=True, hide_parameters=True, echo=False)
    return engine, async_sessionmaker(engine, expire_on_commit=False)
