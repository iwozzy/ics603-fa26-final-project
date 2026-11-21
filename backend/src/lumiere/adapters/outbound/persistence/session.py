from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_sessions(url: str, *, pool_size: int = 5, max_overflow: int = 5) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(url, pool_size=pool_size, max_overflow=max_overflow, pool_pre_ping=True, hide_parameters=True, echo=False)
    return engine, async_sessionmaker(engine, expire_on_commit=False)
