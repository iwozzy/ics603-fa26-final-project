import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from lumiere.application.use_cases.guest_sessions import GuestSessionsService
from lumiere.application.use_cases.search_people import SearchPeople
from lumiere.application.use_cases.usage_admission import UsageAdmissionService
from lumiere.domain.access import AttemptOutcome, GuestContext, UsagePolicy
from lumiere.domain.errors import SearchFailed
from lumiere.domain.people import PersonSummary
from tests.fakes.access import MemoryAccess
from tests.fakes.search import FakeClock

NOW = datetime(2026, 11, 15, 23, 59, tzinfo=UTC)
POLICY = UsagePolicy(100, 100, 100, 100, 2, 2, 2, 3, 3, 3)
CONTEXT = GuestContext(uuid4(), uuid4(), "synthetic-ip")


async def test_admission_commits_before_provider_and_rolls_back_failure() -> None:
    store = MemoryAccess()
    service = UsageAdmissionService(store, POLICY)
    await service.admit(CONTEXT, NOW)
    assert store.commits == 1
    await service.admit(CONTEXT, NOW)
    before = store.counts.copy()
    with pytest.raises(SearchFailed):
        await service.admit(CONTEXT, NOW)
    assert store.counts == before
    assert store.rollbacks == 1

    class Catalog:
        async def search_first_page(self, query: str) -> tuple[PersonSummary, ...]:
            assert not store.active
            return ()

    await SearchPeople(Catalog(), UsageAdmissionService(store, replace(POLICY, global_provider_daily=10, session_provider_daily=10, ip_provider_daily=10)), FakeClock()).execute("Tom", CONTEXT)


async def test_idempotent_mark_finish_and_no_refund_after_dispatch() -> None:
    store = MemoryAccess()
    service = UsageAdmissionService(store, POLICY)
    reservation = await service.admit(CONTEXT, NOW)
    counts = store.counts.copy()
    await service.mark_dispatched(reservation)
    await service.mark_dispatched(reservation)
    await service.release_undispatched(reservation)
    await service.finish(reservation, AttemptOutcome.FAILED)
    await service.finish(reservation, AttemptOutcome.SUCCESS)
    await service.release_undispatched(reservation)
    assert store.counts == counts
    assert store.records[reservation.id].state == "failed"


async def test_proven_undispatched_releases_provider_only_once() -> None:
    store = MemoryAccess()
    service = UsageAdmissionService(store, POLICY)
    reservation = await service.admit(CONTEXT, NOW)
    await service.release_undispatched(reservation)
    await service.release_undispatched(reservation)
    await service.mark_dispatched(reservation)
    assert all(count == (1 if key.feature == "people_request" else 0) for key, count in store.counts.items())
    assert store.records[reservation.id].state == "released"


async def test_concurrent_cap_and_utc_rollover_keeps_total_cap() -> None:
    store = MemoryAccess()
    service = UsageAdmissionService(store, POLICY)
    results = await asyncio.gather(*(service.admit(CONTEXT, NOW) for _ in range(20)), return_exceptions=True)
    assert sum(not isinstance(result, BaseException) for result in results) == 2
    await service.admit(CONTEXT, NOW + timedelta(days=1))
    with pytest.raises(SearchFailed):
        await UsageAdmissionService(store, POLICY).admit(CONTEXT, NOW + timedelta(days=1))


@pytest.mark.parametrize("field", ["global_requests_per_minute", "session_requests_per_minute", "ip_requests_per_minute", "global_provider_daily", "session_provider_daily", "ip_provider_daily", "global_provider_total", "session_provider_total", "ip_provider_total"])
async def test_each_scope_is_enforced_atomically(field: str) -> None:
    store = MemoryAccess()
    service = UsageAdmissionService(store, replace(POLICY, **{field: 1}))
    await service.admit(CONTEXT, NOW)
    counts = store.counts.copy()
    with pytest.raises(SearchFailed):
        await service.admit(CONTEXT, NOW)
    assert store.counts == counts


async def test_sessions_reuse_expire_and_use_current_ip() -> None:
    store = MemoryAccess()
    service = GuestSessionsService(store, POLICY)
    first = await service.bootstrap(None, "ip-a", NOW)
    reused = await service.bootstrap(first.proof, "ip-b", NOW)
    assert first.is_new and not reused.is_new
    assert reused.context.profile_id == first.context.profile_id
    assert reused.context.ip_key == "ip-b"
    resolved = await service.resolve(first.proof, "ip-c", NOW)
    assert resolved.ip_key == "ip-c"
    assert first.proof.encode() not in store.tokens
    assert len(next(iter(store.tokens))) == 32
    with pytest.raises(SearchFailed):
        await service.resolve(first.proof, "ip-a", NOW + timedelta(days=1))
    assert (await service.bootstrap(first.proof, "ip-a", NOW + timedelta(days=1))).is_new


async def test_bootstrap_limit_and_missing_session_fail_closed() -> None:
    store = MemoryAccess()
    service = GuestSessionsService(store, replace(POLICY, bootstrap_requests_per_ip_per_minute=1))
    await service.bootstrap(None, "ip", NOW)
    with pytest.raises(SearchFailed):
        await service.bootstrap(None, "ip", NOW)
    with pytest.raises(SearchFailed):
        await service.resolve(None, "ip", NOW)
    assert len(store.tokens) == 1
