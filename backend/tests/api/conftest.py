from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest
from asgi_lifespan import LifespanManager

from lumiere.adapters.inbound.http.deps import HttpServices
from lumiere.application.use_cases.following import (
    FollowPerson,
    ListFollowing,
    UnfollowPerson,
)
from lumiere.application.use_cases.guest_identity import GuestIdentityService
from lumiere.application.use_cases.search_people import SearchPeople
from lumiere.domain.access import UsagePolicy
from lumiere.main import create_app
from tests.fakes.access import MemoryAccess
from tests.fakes.following import MemoryFollowing
from tests.fakes.hydration import RecordingFilmographyQueue
from tests.fakes.search import (
    FakeAdmission,
    FakeCatalog,
    FakeClock,
    FakePeopleQueue,
    sample_person,
)


@dataclass
class Api:
    client: httpx.AsyncClient
    catalog: FakeCatalog
    admission: FakeAdmission
    services: HttpServices
    following: MemoryFollowing
    access: MemoryAccess


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    catalog = FakeCatalog((sample_person(known_for=("Alien",)),))
    admission = FakeAdmission()
    access = MemoryAccess()
    following = MemoryFollowing()
    sessions = GuestIdentityService(access, UsagePolicy(100,100,100,100,100,100,100,100,100,100))
    services = HttpServices(SearchPeople(catalog, admission, FakeClock(), FakePeopleQueue()), sessions, b"synthetic-test-key", list_following=ListFollowing(following), follow_person=FollowPerson(following, RecordingFilmographyQueue()), unfollow_person=UnfollowPerson(following))
    app = create_app(services)
    async with LifespanManager(app), httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="https://app.test") as client:
        yield Api(client, catalog, admission, services, following, access)
