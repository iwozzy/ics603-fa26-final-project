import httpx
import pytest

from lumiere.domain.errors import SearchFailed
from tests.api.conftest import Api


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
        assert set(response.json()["people"][0]) == {"name", "department", "profile_image_url", "known_for"}


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
    from lumiere.domain.people import PersonSummary

    await api.client.post("/api/v1/guest-session")
    api.catalog.people = (PersonSummary("", None, None, ("A", "B", "C", "D")),)
    response = await api.client.get("/api/v1/people/search?query=Tom")
    assert response.status_code == 500
    assert response.content == b"" and response.headers["cache-control"] == "no-store"


async def test_unhandled_session_failure_is_empty_500(api: Api) -> None:
    from dataclasses import replace
    from datetime import datetime

    from lumiere.domain.access import GuestContext, GuestSession
    from lumiere.main import create_app

    class BrokenSessions:
        async def bootstrap(self, proof: str | None, ip_key: str, now: datetime) -> GuestSession:
            raise RuntimeError("synthetic")

        async def resolve(self, proof: str | None, ip_key: str, now: datetime) -> GuestContext:
            raise RuntimeError("synthetic")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(replace(api.services, sessions=BrokenSessions())), raise_app_exceptions=False), base_url="https://app.test") as client:
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
