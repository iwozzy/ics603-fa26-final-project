import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest

from lumiere.application.use_cases.search_people import SearchPeople
from lumiere.application.use_cases.usage_admission import UsageAdmissionService
from lumiere.domain.access import GuestContext, UsagePolicy
from lumiere.domain.errors import SearchFailed
from lumiere.domain.people import PersonSummary
from tests.fakes.accounting import ControlledAccess
from tests.fakes.search import FakeClock, sample_person

POLICY = UsagePolicy(*(100 for _ in range(10)))
CONTEXT = GuestContext(uuid4(), "synthetic-ip")


@pytest.mark.parametrize("error", [None, RuntimeError("synthetic"), asyncio.CancelledError()])
async def test_provider_outcome_keeps_local_charge_and_persists_asynchronously(error: BaseException | None) -> None:
    store = ControlledAccess()
    store.allow_flush.clear()
    admission = UsageAdmissionService(store, replace(POLICY, global_provider_total=1))
    await admission.start(FakeClock().now())

    class Catalog:
        async def search_first_page(self, query: str) -> tuple[PersonSummary, ...]:
            assert store.counts == {}
            # The local allowance was charged before provider dispatch.
            with pytest.raises(SearchFailed, match="quota"):
                await admission.admit_and_charge(CONTEXT, FakeClock().now())
            if error is not None:
                raise error
            return (sample_person(),)

    try:
        search = SearchPeople(Catalog(), admission, FakeClock())
        if isinstance(error, asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await search.execute("Tom", CONTEXT)
        elif error is not None:
            with pytest.raises(SearchFailed, match="provider"):
                await search.execute("Tom", CONTEXT)
        else:
            assert (await search.execute("Tom", CONTEXT)).people[0].name == "Tom"
    finally:
        store.allow_flush.set()
        await admission.close()
    assert len(store.counts) == 6
    assert set(store.counts.values()) == {1}


async def test_cancelling_request_during_provider_does_not_cancel_persistence() -> None:
    store = ControlledAccess()
    store.allow_flush.clear()
    started = asyncio.Event()
    admission = UsageAdmissionService(store, POLICY)
    await admission.start(FakeClock().now())

    class Catalog:
        async def search_first_page(self, query: str) -> tuple[PersonSummary, ...]:
            started.set()
            await asyncio.Event().wait()
            return ()

    task = asyncio.create_task(SearchPeople(Catalog(), admission, FakeClock()).execute("Tom", CONTEXT))
    try:
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 0.2)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        store.allow_flush.set()
        await admission.close()
    assert set(store.counts.values()) == {1}
