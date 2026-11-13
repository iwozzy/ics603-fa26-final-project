"""Local runtime composition. Only bind one worker to loopback until release gates close."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi.staticfiles import StaticFiles

from .api import create_api
from .config import Settings


def configure_logging():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for name in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(name).disabled = True


def create_app():
    configure_logging()
    settings = Settings.from_env()
    if not settings.tmdb_token:
        raise RuntimeError("Set TMDB_API_READ_ACCESS_TOKEN before starting the API")
    client = httpx.AsyncClient(
        follow_redirects=False, transport=httpx.AsyncHTTPTransport(retries=0)
    )
    app = create_api(settings, client)

    @asynccontextmanager
    async def lifespan(app):
        async with client:
            yield

    app.router.lifespan_context = lifespan
    static = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True))
    return app
