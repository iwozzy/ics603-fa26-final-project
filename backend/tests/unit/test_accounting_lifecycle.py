import asyncio
from typing import cast
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from lumiere.adapters.inbound.http.deps import HttpServices
from lumiere.application.use_cases.guest_identity import GuestIdentityService
from lumiere.application.use_cases.search_people import SearchPeople
from lumiere.application.use_cases.usage_admission import UsageAdmissionService
from lumiere.bootstrap import AppContainer
from lumiere.domain.access import CounterKey, GuestContext, UsagePolicy
from lumiere.domain.errors import SearchFailed
from tests.fakes.access import MemoryUow
from tests.fakes.accounting import ControlledAccess
from tests.fakes.search import FakeCatalog, FakeClock

POLICY = UsagePolicy(*(100 for _ in range(10)))
TOTAL = CounterKey("global", "all", "people_provider", "total")
NOW = FakeClock().now()
CONTEXT = GuestContext(uuid4(), "synthetic-ip")


class EngineProbe:
    def __init__(self, access: ControlledAccess) -> None:
        self.access = access
        self.disposed = False

    async def dispose(self) -> None:
        assert not self.access.active
        self.disposed = True


def make_container(access: ControlledAccess, admission: UsageAdmissionService, probe: EngineProbe) -> AppContainer:
    services = HttpServices(SearchPeople(FakeCatalog(), admission, FakeClock()), GuestIdentityService(access, POLICY), b"synthetic-test-key")
    return AppContainer(services, httpx.AsyncClient(), cast(AsyncEngine, probe), admission)


async def test_container_hydrates_before_serving_and_drains_before_disposal() -> None:
    access = ControlledAccess()
    access.counts[TOTAL] = 3
    admission = UsageAdmissionService(access, POLICY)
    probe = EngineProbe(access)
    container = make_container(access, admission, probe)
    try:
        await container.startup()
        access.allow_flush.clear()
        await admission.admit_and_charge(CONTEXT, NOW)
        await asyncio.wait_for(access.entered.wait(), 1)
        closing = asyncio.create_task(container.close())
        await asyncio.sleep(0)
        assert not probe.disposed
        with pytest.raises(SearchFailed, match="storage"):
            await admission.admit_and_charge(CONTEXT, NOW)
        access.allow_flush.set()
        await asyncio.wait_for(closing, 1)
        assert access.counts[TOTAL] == 4
        assert container.client.is_closed
        assert probe.disposed
    finally:
        access.allow_flush.set()
        await container.close()


async def test_container_cleans_up_after_startup_failure() -> None:
    access = ControlledAccess()

    def unavailable() -> MemoryUow:
        raise SearchFailed("storage")

    admission = UsageAdmissionService(unavailable, POLICY)
    probe = EngineProbe(access)
    container = make_container(access, admission, probe)
    try:
        with pytest.raises(SearchFailed, match="storage"):
            await container.startup()
    finally:
        await container.close()
    assert container.client.is_closed
    assert probe.disposed
