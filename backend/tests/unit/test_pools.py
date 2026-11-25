from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from lumiere.adapters.outbound.persistence import pools


async def test_register_creates_independent_lazy_pools() -> None:
    registry = pools.PoolRegistry()
    application = registry.register('application', 'postgresql+psycopg://unused@127.0.0.1:1/unused')
    people = registry.register('people_writer', 'postgresql+psycopg://unused@127.0.0.1:1/unused')
    try:
        assert application.engine is not people.engine
        assert registry.get('people_writer').sessions is people.sessions
        for pool in (application, people):
            assert pool.engine.pool.size() == 5  # type: ignore[attr-defined]
            assert pool.engine.pool.checkedout() == 0  # type: ignore[attr-defined]
            assert pool.engine.pool._max_overflow == 5  # type: ignore[attr-defined]
    finally:
        await registry.close()


def test_duplicate_name_does_not_create_an_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, int, int]] = []
    def factory(url: str, *, pool_size: int, max_overflow: int) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
        calls.append((url, pool_size, max_overflow))
        return cast(AsyncEngine, AsyncMock()), async_sessionmaker()
    monkeypatch.setattr(pools, 'create_sessions', factory)
    registry = pools.PoolRegistry()
    registry.register('application', 'application')
    registry.register('people_writer', 'people_writer')
    with pytest.raises(ValueError):
        registry.register('application', 'duplicate')
    assert calls == [('application', 5, 5), ('people_writer', 5, 5)]


def test_unknown_pool_raises_key_error() -> None:
    with pytest.raises(KeyError):
        pools.PoolRegistry().get('missing')


async def test_close_disposes_all_pools_even_after_one_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    engines = [AsyncMock(), AsyncMock()]
    engines[0].dispose.side_effect = RuntimeError('synthetic')
    def factory(url: str, *, pool_size: int, max_overflow: int) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
        return cast(AsyncEngine, engines[int(url)]), async_sessionmaker()
    monkeypatch.setattr(pools, 'create_sessions', factory)
    registry = pools.PoolRegistry()
    registry.register('first', '0')
    registry.register('second', '1')
    with pytest.raises(ExceptionGroup):
        await registry.close()
    await registry.close()
    assert [engine.dispose.await_count for engine in engines] == [1, 1]
