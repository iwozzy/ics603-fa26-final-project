import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork
from lumiere.application.use_cases.usage_admission import UsageAdmissionService
from lumiere.domain.access import CounterKey, GuestContext, UsagePolicy
from lumiere.domain.errors import SearchFailed
from tests.fakes.accounting import running_accounting

POLICY = UsagePolicy(100, 100, 100, 100, 2, 2, 2, 3, 3, 3)
NOW = datetime(2026, 11, 15, 23, 59, tzinfo=UTC)
CONTEXT = GuestContext(uuid4(), "synthetic-ip")


async def test_concurrent_cap_and_restart(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    async with running_accounting(uows, POLICY, NOW) as service:
        results = await asyncio.gather(*(service.admit_and_charge(CONTEXT, NOW) for _ in range(20)), return_exceptions=True)
    assert sum(not isinstance(result, BaseException) for result in results) == 2
    assert all(not isinstance(result, BaseException) or isinstance(result, SearchFailed) for result in results)
    async with uows() as uow:
        key = CounterKey("global", "all", "people_provider", "total")
        assert (await uow.usage.lock_counters((key,)))[key] == 2
    async with running_accounting(uows, POLICY, NOW) as restarted:
        with pytest.raises(SearchFailed):
            await restarted.admit_and_charge(CONTEXT, NOW)


async def test_utc_rollover_keeps_total_cap(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    async with running_accounting(uows, POLICY, NOW) as service:
        await service.admit_and_charge(CONTEXT, NOW)
        await service.admit_and_charge(CONTEXT, NOW)
        await service.admit_and_charge(CONTEXT, NOW + timedelta(minutes=2))
        with pytest.raises(SearchFailed):
            await service.admit_and_charge(CONTEXT, NOW + timedelta(minutes=2))


async def test_storage_outage_blocks_dispatch() -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from lumiere.application.use_cases.search_people import SearchPeople
    from tests.fakes.search import FakeCatalog, FakeClock

    engine = create_async_engine("postgresql+psycopg://lumiere_test@127.0.0.1:1/lumiere_test", connect_args={"connect_timeout": 1}, hide_parameters=True)
    factory = async_sessionmaker(engine)
    catalog = FakeCatalog()
    service = UsageAdmissionService(lambda: PostgresAccessUnitOfWork(factory), POLICY)
    with pytest.raises(SearchFailed):
        await service.start(NOW)
    with pytest.raises(SearchFailed):
        await SearchPeople(catalog, service, FakeClock()).execute("Tom", CONTEXT)
    assert catalog.queries == []
    await engine.dispose()
