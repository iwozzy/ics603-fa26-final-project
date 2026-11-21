import httpx
import pytest

from lumiere.domain.errors import SearchFailed
from tests.api.conftest import Api
from tests.fakes.search import FakePeopleQueue, sample_person


@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.parametrize("seconds", [10, 10001])
async def test_success_uses_configured_cache_lifetime(api: Api, empty: bool, seconds: int) -> None:
    from dataclasses import replace

    from lumiere.main import create_app

    if empty:
        api.catalog.people = ()
    app = create_app(replace(api.services, search_cache_max_age_seconds=seconds))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://app.test") as client:
        await client.post("/api/v1/guest-session")
        response = await client.get("/api/v1/people/search?query=Tom")
    assert response.status_code == 200
    assert response.headers["cache-control"] == f"private, max-age={seconds}"
    assert "cookie" not in response.headers.get("vary", "").lower()
    assert "set-cookie" not in response.headers
    if empty:
        assert response.json()["people"] == []


@pytest.mark.parametrize("empty", [False, True])
async def test_success_and_empty_success_headers(api: Api, empty: bool) -> None:
    await api.client.post("/api/v1/guest-session")
    if empty:
        api.catalog.people = ()
    response = await api.client.get("/api/v1/people/search", params={"query": " Tom "})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, max-age=300"
    assert "cookie" not in response.headers.get("vary", "").lower()
    assert "set-cookie" not in response.headers
    assert set(response.json()) == {"query", "people"}
    assert response.json()["query"] == "Tom"
    if empty:
        assert response.json()["people"] == []
    else:
        assert set(response.json()["people"][0]) == {"provider", "provider_id", "name", "known_for_department", "profile_image_url", "known_for"}


@pytest.mark.parametrize("kind", ["missing", "blank", "long", "session", "quota", "storage", "provider", "timeout", "unhandled"])
async def test_every_failure_is_empty_500(api: Api, kind: str) -> None:
    if kind != "session":
        await api.client.post("/api/v1/guest-session")
    if kind in ("quota", "storage"):
        api.admission.error = SearchFailed(kind)
    if kind in ("provider", "timeout", "unhandled"):
        api.catalog.error = {"provider": SearchFailed("provider"), "timeout": TimeoutError(), "unhandled": RuntimeError("synthetic")}[kind]
    query = {"missing": None, "blank": "   ", "long": "😀" * 201}.get(kind, "Tom")
    response = await api.client.get("/api/v1/people/search", params={"query": query} if query is not None else {})
    assert response.status_code == 500
    assert response.content == b""
    assert response.headers["cache-control"] == "no-store"
    if kind not in ("provider", "timeout", "unhandled"):
        assert api.catalog.queries == []


async def test_invalid_output_is_empty_500(api: Api) -> None:

    await api.client.post("/api/v1/guest-session")
    api.catalog.people = (sample_person(name="", known_for=("A", "B", "C", "D")),)
    response = await api.client.get("/api/v1/people/search?query=Tom")
    assert response.status_code == 500
    assert response.content == b"" and response.headers["cache-control"] == "no-store"


async def test_unhandled_session_failure_is_empty_500(api: Api) -> None:
    from dataclasses import replace
    from datetime import datetime

    from lumiere.domain.access import GuestBootstrap, GuestContext
    from lumiere.main import create_app

    class BrokenSessions:
        async def bootstrap(self, proof: str | None, ip_key: str, now: datetime) -> GuestBootstrap:
            raise RuntimeError("synthetic")

        async def resolve(self, proof: str | None, ip_key: str, now: datetime) -> GuestContext:
            raise RuntimeError("synthetic")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(replace(api.services, guests=BrokenSessions())), raise_app_exceptions=False), base_url="https://app.test") as client:
        response = await client.get("/api/v1/people/search?query=Tom")
    assert response.status_code == 500
    assert response.content == b"" and response.headers["cache-control"] == "no-store"


async def test_application_deadline_cancels_work(api: Api) -> None:
    import asyncio
    from dataclasses import replace
    from time import monotonic

    from lumiere.domain.access import GuestContext
    from lumiere.domain.people import SearchPeopleResult
    from lumiere.main import create_app

    cancelled = asyncio.Event()

    class SlowSearch:
        async def execute(self, raw_query: str, context: GuestContext) -> SearchPeopleResult:
            try:
                await asyncio.sleep(9)
            except asyncio.CancelledError:
                cancelled.set()
                raise
            return SearchPeopleResult(raw_query, ())

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(replace(api.services, search_people=SlowSearch()))), base_url="https://app.test") as client:
        await client.post("/api/v1/guest-session")
        start = monotonic()
        response = await client.get("/api/v1/people/search?query=Tom")
        assert response.status_code == 500 and response.content == b""
        assert response.headers["cache-control"] == "no-store"
        assert monotonic() - start < 8
        assert cancelled.is_set()


async def test_real_search_deadline_preserves_admission_charge(api: Api) -> None:
    import asyncio
    from dataclasses import replace
    from datetime import datetime
    from time import monotonic
    from typing import override

    from lumiere.application.use_cases.search_people import SearchPeople
    from lumiere.domain.access import GuestContext
    from lumiere.domain.people import PersonSummary
    from lumiere.main import create_app
    from tests.fakes.search import FakeAdmission, FakeClock

    cancelled = asyncio.Event()

    class SlowAdmission(FakeAdmission):
        @override
        async def admit_and_charge(self, context: GuestContext, now: datetime) -> None:
            await asyncio.sleep(3)
            await super().admit_and_charge(context, now)

    class BoundedProvider:
        async def search_first_page(self, query: str) -> tuple[PersonSummary, ...]:
            try:
                async with asyncio.timeout(5):
                    await asyncio.sleep(10)
            except asyncio.CancelledError:
                cancelled.set()
                raise
            return ()

    admission = SlowAdmission()
    app = create_app(replace(api.services, search_people=SearchPeople(BoundedProvider(), admission, FakeClock(), FakePeopleQueue())))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://app.test") as client:
        await client.post("/api/v1/guest-session")
        start = monotonic()
        response = await client.get("/api/v1/people/search?query=Tom")
        assert response.status_code == 500 and response.content == b""
        assert response.headers["cache-control"] == "no-store"
        assert monotonic() - start < 8
        assert admission.admissions == 1
        await asyncio.wait_for(cancelled.wait(), 1)


async def test_http_deadline_returns_while_cancelled_dependency_cleans_up() -> None:
    import asyncio
    from time import monotonic

    from starlette.responses import Response
    from starlette.types import Receive, Scope, Send

    from lumiere.adapters.inbound.http.errors import FailureBoundary

    cleaned = asyncio.Event()

    async def slow(scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            await asyncio.sleep(0.1)
        await Response()(scope, receive, send)
        cleaned.set()

    boundary = FailureBoundary(slow, deadline=0.02)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=boundary), base_url="https://app.test") as client:
        start = monotonic()
        response = await client.get("/api/v1/people/search?query=Tom")
        assert response.status_code == 500 and response.headers["cache-control"] == "no-store"
        assert monotonic() - start < 0.15
        await asyncio.wait_for(cleaned.wait(), 1)


@pytest.mark.parametrize('kind', ['full', 'stopped', 'broken'])
async def test_unavailable_people_queue_keeps_success_and_cache_headers(api: Api, kind: str) -> None:
    from dataclasses import replace

    from lumiere.application.use_cases.search_people import SearchPeople
    from lumiere.main import create_app
    from tests.fakes.search import FakeClock, FakePeopleQueue
    queue = FakePeopleQueue(accepted=False, error=RuntimeError('synthetic') if kind == 'broken' else None)
    app = create_app(replace(api.services, search_people=SearchPeople(api.catalog, api.admission, FakeClock(), queue)))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://app.test') as client:
        await client.post('/api/v1/guest-session')
        response = await client.get('/api/v1/people/search?query=Tom')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'private, max-age=300'
    assert response.json()['people'][0]['provider_id'] == 4139
