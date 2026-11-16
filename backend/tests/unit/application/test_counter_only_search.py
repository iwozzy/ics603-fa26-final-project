import asyncio
from datetime import UTC, datetime
from typing import override
from uuid import uuid4

import pytest

from lumiere.application.use_cases.search_people import SearchPeople
from lumiere.application.use_cases.usage_admission import UsageAdmissionService
from lumiere.domain.access import GuestContext, UsagePolicy
from lumiere.domain.errors import SearchFailed
from lumiere.domain.people import PersonSummary
from tests.fakes.access import MemoryAccess, MemoryUow
from tests.fakes.search import FakeCatalog, FakeClock

POLICY = UsagePolicy(100, 100, 100, 100, 100, 100, 100, 100, 100, 100)
CONTEXT = GuestContext(uuid4(), "synthetic-ip")


@pytest.mark.parametrize("error", [None, RuntimeError("synthetic"), asyncio.CancelledError()])
async def test_search_charges_once_without_post_provider_database_access(error: BaseException | None) -> None:
    store = MemoryAccess()
    provider_started = False
    database_opens_after_provider = 0

    def uows() -> MemoryUow:
        nonlocal database_opens_after_provider
        if provider_started:
            database_opens_after_provider += 1
        return store()

    class Catalog:
        async def search_first_page(self, query: str) -> tuple[PersonSummary, ...]:
            nonlocal provider_started
            assert store.commits == 1
            assert not store.active
            assert len(store.counts) == 9
            assert set(store.counts.values()) == {1}
            provider_started = True
            if error is not None:
                raise error
            return (PersonSummary("Tom", None, None, ()),)

    search = SearchPeople(Catalog(), UsageAdmissionService(uows, POLICY), FakeClock())
    if isinstance(error, asyncio.CancelledError):
        with pytest.raises(asyncio.CancelledError):
            await search.execute("Tom", CONTEXT)
    elif error is not None:
        with pytest.raises(SearchFailed, match="provider"):
            await search.execute("Tom", CONTEXT)
    else:
        assert (await search.execute("Tom", CONTEXT)).people[0].name == "Tom"
    # Let any incorrectly queued settlement task run before checking storage.
    await asyncio.sleep(0)
    assert database_opens_after_provider == 0
    assert store.commits == 1
    assert len(store.counts) == 9
    assert set(store.counts.values()) == {1}


async def test_admission_returns_after_committing_counters() -> None:
    store = MemoryAccess()
    result = await UsageAdmissionService(store, POLICY).admit_and_charge(CONTEXT, datetime(2026, 11, 15, tzinfo=UTC))
    assert result is None
    assert store.commits == 1
    assert len(store.counts) == 9
    assert set(store.counts.values()) == {1}


async def test_ambiguous_commit_never_dispatches_or_refunds() -> None:
    store = MemoryAccess()

    class AmbiguousUow(MemoryUow):
        @override
        async def commit(self) -> None:
            await super().commit()
            raise SearchFailed("storage")

    admission = UsageAdmissionService(lambda: AmbiguousUow(store), POLICY)
    catalog = FakeCatalog()
    with pytest.raises(SearchFailed, match="storage"):
        await SearchPeople(catalog, admission, FakeClock()).execute("Tom", CONTEXT)
    assert catalog.queries == []
    assert store.commits == 1
    assert len(store.counts) == 9
    assert set(store.counts.values()) == {1}


async def test_cancellation_during_provider_keeps_committed_charge() -> None:
    store = MemoryAccess()
    started = asyncio.Event()
    opens = 0

    def uows() -> MemoryUow:
        nonlocal opens
        opens += 1
        return store()

    class Catalog:
        async def search_first_page(self, query: str) -> tuple[PersonSummary, ...]:
            started.set()
            await asyncio.Event().wait()
            return ()

    task = asyncio.create_task(SearchPeople(Catalog(), UsageAdmissionService(uows, POLICY), FakeClock()).execute("Tom", CONTEXT))
    await asyncio.wait_for(started.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 0.2)
    await asyncio.sleep(0)
    assert opens == 1
    assert store.commits == 1
    assert set(store.counts.values()) == {1}
