"""Local runtime composition. Only bind one worker to loopback until release gates close."""

import logging
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .admission import LocalAdmission
from .api import create_api
from .config import Settings
from .search import search_people
from .tmdb import TmdbPeople


def configure_logging():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for name in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(name).disabled = True


def compose_api(settings: Settings, client: httpx.AsyncClient) -> FastAPI:
    """Select concrete adapters once, shared by local startup and integration tests."""
    incoming = LocalAdmission(
        settings.incoming_concurrency,
        settings.admissions_per_minute,
        settings.admission_total,
    )
    outgoing = LocalAdmission(
        settings.outgoing_concurrency,
        settings.admissions_per_minute,
        settings.admission_total,
    )
    provider = TmdbPeople(client, settings, outgoing)
    search = partial(
        search_people, provider=provider, max_query_chars=settings.max_query_chars
    )
    return create_api(
        settings,
        search,
        incoming,
        lambda: {
            "incoming_admitted": incoming.admitted,
            "provider_attempts": outgoing.admitted,
        },
    )


def create_app():
    configure_logging()
    settings = Settings.from_env()
    if not settings.tmdb_token:
        raise RuntimeError("Set TMDB_API_READ_ACCESS_TOKEN before starting the API")
    client = httpx.AsyncClient(
        follow_redirects=False, transport=httpx.AsyncHTTPTransport(retries=0)
    )
    app = compose_api(settings, client)

    @asynccontextmanager
    async def lifespan(app):
        async with client:
            yield

    app.router.lifespan_context = lifespan
    static = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True))
    return app
