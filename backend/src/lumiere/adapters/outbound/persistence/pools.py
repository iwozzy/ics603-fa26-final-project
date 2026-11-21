from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from lumiere.adapters.outbound.persistence.session import create_sessions


@dataclass(frozen=True)
class DatabasePool:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]


class PoolRegistry:
    def __init__(self) -> None:
        self._pools: dict[str, DatabasePool] = {}

    def register(self, name: str, url: str, *, pool_size: int = 5, max_overflow: int = 5) -> DatabasePool:
        if name in self._pools:
            raise ValueError("pool already registered")
        engine, sessions = create_sessions(url, pool_size=pool_size, max_overflow=max_overflow)
        pool = DatabasePool(engine, sessions)
        self._pools[name] = pool
        return pool

    def get(self, name: str) -> DatabasePool:
        return self._pools[name]

    async def close(self) -> None:
        pools = self._pools
        self._pools = {}
        errors: list[Exception] = []
        for pool in pools.values():
            try:
                await pool.engine.dispose()
            except Exception as error:  # noqa: BLE001 — finish every disposal
                errors.append(error)
        if errors:
            raise ExceptionGroup("pool disposal failed", errors)
