import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from lumiere.application.use_cases.guest_identity import GuestIdentityService
from lumiere.application.use_cases.search_people import SearchPeople
from lumiere.application.use_cases.usage_admission import UsageAdmissionService
from lumiere.domain.access import CounterKey, GuestContext, UsagePolicy
from lumiere.domain.errors import SearchFailed
from tests.fakes.access import MemoryUow
from tests.fakes.accounting import ControlledAccess
from tests.fakes.search import FakeCatalog, FakeClock

NOW = datetime(2026, 11, 15, 23, 59, tzinfo=UTC)
CONTEXT = GuestContext(uuid4(), "synthetic-ip")
POLICY = UsagePolicy(*(100 for _ in range(10)))
TOTAL = CounterKey("global", "all", "people_provider", "total")


@pytest.fixture
async def running() -> AsyncIterator[tuple[ControlledAccess, UsageAdmissionService]]:
    access = ControlledAccess()
    service = UsageAdmissionService(access, POLICY, retry_delay=0.001)
    await service.start(NOW)
    try:
        yield access, service
    finally:
        access.allow_flush.set()
        await service.close()


async def test_unstarted_admission_fails_closed_without_dispatch() -> None:
    access, catalog = ControlledAccess(), FakeCatalog()
    service = UsageAdmissionService(access, POLICY)
    with pytest.raises(SearchFailed, match="storage"):
        await SearchPeople(catalog, service, FakeClock()).execute("Tom", CONTEXT)
    assert catalog.queries == []
    assert access.opens == 0


async def test_search_returns_while_persistence_is_blocked(running: tuple[ControlledAccess, UsageAdmissionService]) -> None:
    access, service = running
    access.allow_flush.clear()
    await service.admit_and_charge(CONTEXT, NOW)
    await asyncio.wait_for(access.entered.wait(), 1)
    opens = access.opens
    catalog = FakeCatalog()
    await asyncio.wait_for(SearchPeople(catalog, service, FakeClock()).execute("Tom", CONTEXT), 0.2)
    assert catalog.queries == ["Tom"]
    assert access.opens == opens
    assert access.counts == {}


@pytest.mark.parametrize("field", ["global_requests_per_minute", "session_requests_per_minute", "ip_requests_per_minute", "global_provider_daily", "session_provider_daily", "ip_provider_daily", "global_provider_total", "session_provider_total", "ip_provider_total"])
async def test_all_caps_reject_without_partially_charging(field: str) -> None:
    access = ControlledAccess()
    service = UsageAdmissionService(access, replace(POLICY, **{field: 1}))
    await service.start(NOW)
    try:
        await service.admit_and_charge(CONTEXT, NOW)
        with pytest.raises(SearchFailed, match="quota"):
            await service.admit_and_charge(CONTEXT, NOW)
        await asyncio.wait_for(service.drain(), 1)
        assert len(access.counts) == 6
        assert set(access.counts.values()) == {1}
    finally:
        await service.close()


async def test_database_reply_preserves_charges_admitted_during_flush() -> None:
    access = ControlledAccess()
    access.allow_flush.clear()
    service = UsageAdmissionService(access, replace(POLICY, global_provider_total=2), batch_size=1)
    access.block_sequence = 2
    await service.start(NOW)
    try:
        await service.admit_and_charge(CONTEXT, NOW)
        await asyncio.wait_for(access.entered.wait(), 1)
        await service.admit_and_charge(CONTEXT, NOW)
        access.entered.clear()
        access.allow_flush.set()
        await asyncio.wait_for(access.entered.wait(), 1)
        assert access.counts[TOTAL] == 1
        with pytest.raises(SearchFailed, match="quota"):
            await service.admit_and_charge(CONTEXT, NOW)
        access.allow_flush.set()
        await asyncio.wait_for(service.drain(), 1)
        assert access.counts[TOTAL] == 2
        assert access.attempts == [1, 2]
    finally:
        access.allow_flush.set()
        await service.close()


async def test_queue_capacity_includes_inflight_charge_and_rejection_consumes_nothing() -> None:
    access = ControlledAccess()
    access.allow_flush.clear()
    service = UsageAdmissionService(access, POLICY, max_pending=1)
    await service.start(NOW)
    try:
        await service.admit_and_charge(CONTEXT, NOW)
        await asyncio.wait_for(access.entered.wait(), 1)
        with pytest.raises(SearchFailed, match="storage"):
            await service.admit_and_charge(CONTEXT, NOW)
        access.allow_flush.set()
        await asyncio.wait_for(service.drain(), 1)
        assert set(access.counts.values()) == {1}
        await service.admit_and_charge(CONTEXT, NOW)
        await asyncio.wait_for(service.drain(), 1)
        assert set(access.counts.values()) == {2}
    finally:
        access.allow_flush.set()
        await service.close()


@pytest.mark.parametrize("ambiguous", [False, True])
async def test_failed_or_ambiguous_flush_retries_same_batch_without_double_count(ambiguous: bool) -> None:
    access = ControlledAccess()
    access.ambiguous_commits = int(ambiguous)
    access.failures = int(not ambiguous)
    service = UsageAdmissionService(access, POLICY, retry_delay=0.001)
    await service.start(NOW)
    try:
        await service.admit_and_charge(CONTEXT, NOW)
        await asyncio.wait_for(service.drain(), 1)
        assert access.attempts == [1, 1]
        assert set(access.counts.values()) == {1}
    finally:
        await service.close()


async def test_midnight_pending_charges_use_original_day_and_total_cap() -> None:
    access = ControlledAccess()
    access.allow_flush.clear()
    service = UsageAdmissionService(access, replace(POLICY, global_provider_daily=1, global_provider_total=2))
    await service.start(NOW)
    try:
        await service.admit_and_charge(CONTEXT, NOW)
        await asyncio.wait_for(access.entered.wait(), 1)
        await service.admit_and_charge(CONTEXT, NOW + timedelta(minutes=2))
        with pytest.raises(SearchFailed, match="quota"):
            await service.admit_and_charge(CONTEXT, NOW + timedelta(minutes=2))
        access.allow_flush.set()
        await asyncio.wait_for(service.drain(), 1)
        assert access.counts[TOTAL] == 2
        assert access.counts[CounterKey("global", "all", "people_provider", "2026-11-15")] == 1
        assert access.counts[CounterKey("global", "all", "people_provider", "2026-11-16")] == 1
    finally:
        access.allow_flush.set()
        await service.close()


async def test_startup_restores_usage_while_minute_limits_reset() -> None:
    access = ControlledAccess()
    policy = replace(POLICY, global_requests_per_minute=1, global_provider_total=2)
    first = UsageAdmissionService(access, policy)
    await first.start(NOW)
    await first.admit_and_charge(CONTEXT, NOW)
    await first.close()
    second = UsageAdmissionService(access, policy)
    await second.start(NOW)
    try:
        await second.admit_and_charge(CONTEXT, NOW)
        await second.drain()
        with pytest.raises(SearchFailed, match="quota"):
            await second.admit_and_charge(CONTEXT, NOW + timedelta(minutes=1))
        assert access.counts[TOTAL] == 2
        assert all(key.feature == "people_provider" for key in access.counts)
    finally:
        await second.close()


async def test_shutdown_drains_pending_charges_and_rejects_further_searches() -> None:
    access = ControlledAccess()
    service = UsageAdmissionService(access, POLICY)
    await service.start(NOW)
    await service.admit_and_charge(CONTEXT, NOW)
    await service.close()
    assert access.counts[TOTAL] == 1
    assert not access.active
    with pytest.raises(SearchFailed, match="storage"):
        await service.admit_and_charge(CONTEXT, NOW)
    await service.close()


async def test_shutdown_timeout_cancels_blocked_writer() -> None:
    access = ControlledAccess()
    access.allow_flush.clear()
    service = UsageAdmissionService(access, POLICY, shutdown_timeout=0.01)
    await service.start(NOW)
    await service.admit_and_charge(CONTEXT, NOW)
    await asyncio.wait_for(access.entered.wait(), 1)
    await asyncio.wait_for(service.close(), 0.2)
    assert not access.active
    assert access.counts == {}


async def test_bootstrap_minute_limit_never_creates_usage_rows() -> None:
    access = ControlledAccess()
    guests = GuestIdentityService(access, replace(POLICY, bootstrap_requests_per_ip_per_minute=1))
    await guests.bootstrap(None, "synthetic-ip", NOW)
    with pytest.raises(SearchFailed, match="bootstrap_quota"):
        await guests.bootstrap(None, "synthetic-ip", NOW)
    await guests.bootstrap(None, "synthetic-ip", NOW + timedelta(minutes=1))
    assert access.counts == {}
    assert len(access.tokens) == 2


async def test_concurrent_identities_share_global_cap(running: tuple[ControlledAccess, UsageAdmissionService]) -> None:
    access, service = running
    service.policy = replace(POLICY, global_provider_total=2)
    contexts = [GuestContext(uuid4(), f"synthetic-{i}") for i in range(20)]
    results = await asyncio.gather(*(service.admit_and_charge(context, NOW) for context in contexts), return_exceptions=True)
    assert sum(result is None for result in results) == 2
    assert all(result is None or isinstance(result, SearchFailed) for result in results)
    await service.drain()
    assert access.counts[TOTAL] == 2


async def test_startup_storage_failure_does_not_enable_searches() -> None:
    def unavailable() -> MemoryUow:
        raise SearchFailed("storage")

    service = UsageAdmissionService(unavailable, POLICY)
    with pytest.raises(SearchFailed, match="storage"):
        await service.start(NOW)
    with pytest.raises(SearchFailed, match="storage"):
        await service.admit_and_charge(CONTEXT, NOW)
    await service.close()


async def test_flush_timeout_retries_without_losing_charge() -> None:
    access = ControlledAccess()
    access.allow_flush.clear()
    service = UsageAdmissionService(access, POLICY, flush_timeout=0.01, retry_delay=0.001)
    await service.start(NOW)
    try:
        await service.admit_and_charge(CONTEXT, NOW)
        await asyncio.wait_for(access.entered.wait(), 1)
        access.entered.clear()
        # The second attempt proves the blocked first transaction timed out.
        await asyncio.wait_for(access.entered.wait(), 1)
        assert access.attempts == [1, 1]
        access.allow_flush.set()
        await asyncio.wait_for(service.drain(), 1)
        assert access.counts[TOTAL] == 1
    finally:
        access.allow_flush.set()
        await service.close()


async def test_writer_combines_queued_charges_in_bounded_batches() -> None:
    access = ControlledAccess()
    service = UsageAdmissionService(access, POLICY, batch_size=4)
    await service.start(NOW)
    try:
        for _ in range(10):
            await service.admit_and_charge(CONTEXT, NOW)
        await asyncio.wait_for(service.drain(), 1)
        assert access.counts[TOTAL] == 10
        assert access.attempts == [1, 2, 3]
    finally:
        await service.close()
