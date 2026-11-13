"""Deterministic external TMDB transport for public web/API behavior tests only."""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from wayfinder.api import create_api
from wayfinder.config import Settings
from wayfinder.runtime import configure_logging

configure_logging()
scenarios = {}
attempts = []


class LocalTmdbTransport(httpx.AsyncBaseTransport):
    def __init__(self):
        self.transport = httpx.AsyncHTTPTransport(retries=0)

    async def handle_async_request(self, request):
        # Actual HTTP hop; substitute only the external provider origin.
        url = request.url.copy_with(
            scheme="http", host="127.0.0.1", port=8765, path="/__provider"
        )
        return await self.transport.handle_async_request(httpx.Request("GET", url))

    async def aclose(self):
        await self.transport.aclose()


client = httpx.AsyncClient(transport=LocalTmdbTransport())
app = create_api(
    Settings(
        tmdb_token="deterministic-test-token",
        admission_total=10000,
        admissions_per_minute=10000,
    ),
    client,
)


@asynccontextmanager
async def lifespan(app):
    async with client:
        yield


app.router.lifespan_context = lifespan


@app.post("/__test/reset")
async def reset(request: Request):
    scenarios.clear()
    scenarios.update(await request.json())
    attempts.clear()
    return {"ok": True}


@app.get("/__test/attempts")
async def history():
    return attempts


@app.get("/__provider")
async def tmdb(request: Request):
    query = request.query_params.get("query")
    attempts.append(dict(request.query_params))
    scenario = scenarios.get(query, {})
    await asyncio.sleep(scenario.get("delay", 0))
    if "raw" in scenario:
        return Response(scenario["raw"], status_code=scenario.get("status", 200))
    return Response(
        json.dumps(
            scenario.get(
                "payload",
                {
                    "results": [
                        {
                            "id": 4139,
                            "name": "Tom Skerritt",
                            "known_for_department": "Acting",
                            "profile_path": None,
                            "known_for": [
                                {"media_type": "movie", "title": "Alien"},
                                {"media_type": "tv", "name": "Picket Fences"},
                            ],
                        }
                    ]
                },
            )
        ),
        media_type="application/json",
        status_code=scenario.get("status", 200),
    )


app.mount("/", StaticFiles(directory=Path("dist"), html=True))
