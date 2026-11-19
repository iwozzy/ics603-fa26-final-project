from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest
from asgi_lifespan import LifespanManager

from lumiere.adapters.inbound.http.deps import HttpServices
from lumiere.application.use_cases.guest_identity import GuestIdentityService
from lumiere.application.use_cases.search_people import SearchPeople
from lumiere.domain.access import UsagePolicy
from lumiere.domain.people import PersonSummary
from lumiere.main import create_app
from tests.fakes.access import MemoryAccess
from tests.fakes.search import FakeAdmission, FakeCatalog, FakeClock


@dataclass
class Api:
    client: httpx.AsyncClient
    catalog: FakeCatalog
    admission: FakeAdmission
    services: HttpServices


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    catalog = FakeCatalog((PersonSummary("Tom", None, None, ("Alien",)),))
    admission = FakeAdmission()
    sessions = GuestIdentityService(MemoryAccess(), UsagePolicy(100,100,100,100,100,100,100,100,100,100))
    services = HttpServices(SearchPeople(catalog, admission, FakeClock()), sessions, b"synthetic-test-key")
    app = create_app(services)
    async with LifespanManager(app), httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="https://app.test") as client:
        yield Api(client, catalog, admission, services)
