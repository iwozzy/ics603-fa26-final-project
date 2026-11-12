"""Browser-test composition root. Never selected by the production entry point."""

import asyncio
import json
from pathlib import Path

import httpx
from fastapi import FastAPI

from lumiere.adapters.tmdb import TMDBSearch
from lumiere.bootstrap import create_app
from lumiere.config import Settings
from lumiere.domain.people import PersonSummary

BASELINE = json.loads(
    (
        Path(__file__).parents[2] / "docs/samples/api/tmdb/v3/search/person.json"
    ).read_text()
)


class FixtureMetadata:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.releases: dict[str, asyncio.Event] = {}

    async def search_people(self, query: str) -> list[PersonSummary]:
        self.queries.append(query)
        if query.startswith("Slow"):
            await self.releases.setdefault(query, asyncio.Event()).wait()
        status, payload = fixture_response(query)
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(status, json=payload)
            )
        ) as client:
            return await TMDBSearch(client, "fixture").search_people(query)


def fixture_response(query: str) -> tuple[int, dict]:
    if query in {"Failure", "Slow failure"}:
        return 503, {"message": "Fixture failure"}
    if query == "Empty":
        return 200, {"results": []}
    if query == "Unusable":
        return 200, {"results": [None, {}]}
    if query == "Latest":
        return 200, {"results": [{"name": "Latest result"}]}
    if query == "Slow success":
        return 200, {"results": [{"name": "Older result"}]}
    if query == "Long":
        return 200, {
            "results": [
                {
                    "name": "A" * 180,
                    "known_for": [{"media_type": "tv", "name": "Unbroken" * 60}],
                }
            ]
        }
    return 200, BASELINE


def create_fixture_app() -> FastAPI:
    metadata = FixtureMetadata()
    app = create_app(Settings(telemetry_enabled=False), metadata=metadata)

    @app.get("/__test__/requests")
    async def requests() -> list[str]:
        return metadata.queries

    @app.post("/__test__/reset")
    async def reset() -> None:
        for event in metadata.releases.values():
            event.set()
        metadata.queries.clear()
        metadata.releases.clear()

    @app.post("/__test__/release")
    async def release(query: str) -> None:
        metadata.releases.setdefault(query, asyncio.Event()).set()

    return app
