"""API composition root; importing this module performs no runtime setup."""

import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter

import httpx
import logfire
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from lumiere.adapters.http.health import router
from lumiere.adapters.http.people import router as people_router
from lumiere.adapters.tmdb import TMDBSearch
from lumiere.application.search_people import MetadataSearch, SearchPeople
from lumiere.config import Settings

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None, *, metadata: MetadataSearch | None = None
) -> FastAPI:
    settings = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        logging.basicConfig(
            level=settings.log_level,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
        # HTTPX's routine request logs include the full search URL.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        app.state.telemetry = logfire.configure(
            local=True,
            send_to_logfire=settings.telemetry_enabled,
            service_name="lumiere-api",
            console=False,
            inspect_arguments=False,
            metrics=False,
        )
        async with httpx.AsyncClient(timeout=10) as client:
            app.state.search_people = SearchPeople(
                metadata
                if metadata is not None
                else TMDBSearch(client, settings.tmdb_token, app.state.telemetry)
            )
            logger.info("API started")
            yield
        app.state.telemetry.force_flush()
        logger.info("API stopped")

    app = FastAPI(title="Lumiere API", version="0.1.0", lifespan=lifespan)
    app.include_router(router)
    app.include_router(people_router)

    @app.middleware("http")
    async def observe_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = perf_counter()
        # Manual spans exclude URLs, queries and payloads.
        with app.state.telemetry.span("HTTP request", method=request.method) as span:
            try:
                response = await call_next(request)
            except Exception as error:  # noqa: BLE001 -- final HTTP error boundary
                span.set_attribute("error_type", type(error).__name__)
                logger.error("Unhandled request failure type=%s", type(error).__name__)
                response = JSONResponse(
                    status_code=500,
                    content={
                        "code": "INTERNAL_ERROR",
                        "message": "Unable to complete request.",
                    },
                )
            duration_ms = round((perf_counter() - start) * 1000, 2)
            span.set_attribute("status_code", response.status_code)
            span.set_attribute(
                "outcome", "failure" if response.status_code >= 400 else "success"
            )
            span.set_attribute("duration_ms", duration_ms)
            logger.info(
                "HTTP request method=%s status=%s duration_ms=%s",
                request.method,
                response.status_code,
                duration_ms,
            )
            return response

    # Keep CORS outside the error boundary so failures also reach allowed clients.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
    )
    return app
