import httpx
import pytest

from lumiere.application.search_people import SearchFailed
from lumiere.bootstrap import create_app
from lumiere.config import Settings
from lumiere.domain.people import PersonSummary


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class Metadata:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def search_people(self, query: str) -> list[PersonSummary]:
        self.queries.append(query)
        return [
            PersonSummary(name=f"Person {i}", known_for=("Movie",)) for i in range(9)
        ]


@pytest.mark.anyio
async def test_search_http_contract() -> None:
    metadata = Metadata()
    app = create_app(Settings(telemetry_enabled=False), metadata=metadata)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.get(
            "/api/people/search", params={"query": "  Timothée  "}
        )
        schema = (await client.get("/openapi.json")).json()
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, max-age=60"
    assert metadata.queries == ["Timothée"]
    assert response.json() == {
        "results": [
            {
                "name": f"Person {i}",
                "portrait_url": None,
                "department": None,
                "known_for": ["Movie"],
            }
            for i in range(7)
        ]
    }
    assert "200" in schema["paths"]["/api/people/search"]["get"]["responses"]


@pytest.mark.parametrize(
    "params", [{}, {"query": ""}, {"query": " \n"}, {"query": "𠮷" * 101}]
)
@pytest.mark.anyio
async def test_invalid_http_input_is_generic_500_without_metadata_call(
    params: dict,
) -> None:
    metadata = Metadata()
    app = create_app(Settings(telemetry_enabled=False), metadata=metadata)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.get("/api/people/search", params=params)
    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "code": "SEARCH_FAILED",
        "message": "Unable to complete search.",
    }
    assert metadata.queries == []


@pytest.mark.anyio
async def test_provider_failure_is_generic_500_and_documented() -> None:
    class BrokenMetadata:
        async def search_people(self, query: str) -> list[PersonSummary]:
            raise SearchFailed("private upstream payload")

    app = create_app(Settings(telemetry_enabled=False), metadata=BrokenMetadata())
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.get("/api/people/search", params={"query": "name"})
        schema = (await client.get("/openapi.json")).json()
    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "code": "SEARCH_FAILED",
        "message": "Unable to complete search.",
    }
    responses = schema["paths"]["/api/people/search"]["get"]["responses"]
    assert "500" in responses
    assert "422" not in responses
    assert set(schema["components"]["schemas"]["SearchError"]["required"]) == {
        "code",
        "message",
    }
