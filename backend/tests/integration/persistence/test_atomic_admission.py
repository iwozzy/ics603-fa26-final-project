import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select

from lumiere.adapters.outbound.persistence.models import CounterRow
from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork
from lumiere.application.use_cases.usage_admission import (
    UsageAdmissionService,
    admission_limits,
)
from lumiere.domain.access import GuestContext, UsagePolicy
from lumiere.domain.errors import SearchFailed

POLICY = UsagePolicy(100, 100, 100, 100, 100, 100, 100, 100, 100, 100)
NOW = datetime(2026, 11, 15, tzinfo=UTC)
CONTEXT = GuestContext(uuid4(), "synthetic-ip")


async def test_admission_uses_one_database_call_and_rolls_back_without_commit(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    async with uows() as uow:
        connection = await uow.session.connection()
        calls: list[object] = []

        def count_call(*args: object) -> None:
            calls.append(None)

        event.listen(connection.sync_connection, "before_cursor_execute", count_call)
        assert await uow.usage.admit_and_charge(admission_limits(CONTEXT, NOW, POLICY))
        assert len(calls) == 1
        event.remove(connection.sync_connection, "before_cursor_execute", count_call)
    async with uows() as other:
        assert await other.session.scalar(select(func.count()).select_from(CounterRow)) == 0


@pytest.mark.parametrize("field", ["global_requests_per_minute", "session_requests_per_minute", "ip_requests_per_minute", "global_provider_daily", "session_provider_daily", "ip_provider_daily", "global_provider_total", "session_provider_total", "ip_provider_total"])
async def test_every_cap_rejects_without_partial_charges(uows: Callable[[], PostgresAccessUnitOfWork], field: str) -> None:
    admission = UsageAdmissionService(uows, replace(POLICY, **{field: 1}))
    await admission.admit_and_charge(CONTEXT, NOW)
    with pytest.raises(SearchFailed, match="quota"):
        await admission.admit_and_charge(CONTEXT, NOW)
    async with uows() as uow:
        counts = (await uow.session.scalars(select(CounterRow.count))).all()
        assert len(counts) == 9
        assert set(counts) == {1}


async def test_concurrent_different_identities_share_atomic_global_cap(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    admission = UsageAdmissionService(uows, replace(POLICY, global_provider_total=2))
    contexts = [GuestContext(uuid4(), f"synthetic-ip-{i}") for i in range(20)]
    async with asyncio.timeout(10):
        results = await asyncio.gather(*(admission.admit_and_charge(context, NOW) for context in contexts), return_exceptions=True)
    assert sum(result is None for result in results) == 2
    failures = [result for result in results if isinstance(result, BaseException)]
    assert len(failures) == 18
    assert all(isinstance(result, SearchFailed) and str(result) == "quota" for result in failures)
    async with uows() as uow:
        global_counts = (await uow.session.scalars(select(CounterRow.count).where(CounterRow.scope == "global"))).all()
        assert len(global_counts) == 3
        assert set(global_counts) == {2}


async def test_large_configured_caps_do_not_narrow_to_int32(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    policy = UsagePolicy(*(10**12 for _ in range(10)))
    await UsageAdmissionService(uows, policy).admit_and_charge(CONTEXT, NOW)
    async with uows() as uow:
        counts = (await uow.session.scalars(select(CounterRow.count))).all()
        assert len(counts) == 9
        assert set(counts) == {1}
