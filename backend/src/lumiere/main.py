from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from lumiere.adapters.inbound.http.deps import HttpServices
from lumiere.adapters.inbound.http.errors import (
    FailureBoundary,
    http_failure,
    validation_failure,
)
from lumiere.adapters.inbound.http.routers.v1.following import following_router
from lumiere.adapters.inbound.http.routers.v1.guest_session import session_router
from lumiere.adapters.inbound.http.routers.v1.people import people_router
from lumiere.adapters.inbound.http.routers.v1.timeline import timeline_router


def create_app(services: HttpServices) -> FastAPI:
    app = FastAPI(title="Lumiere", version="0.1.0", telemetry={"tracing": False, "metrics": False, "logs": False, "operation_spans": False, "auto_configure": False})
    app.include_router(people_router(services))
    app.include_router(following_router(services))
    app.include_router(timeline_router(services))
    app.include_router(session_router(services))
    app.add_exception_handler(RequestValidationError, validation_failure)  # type: ignore[arg-type]

    app.add_exception_handler(HTTPException, http_failure)  # type: ignore[arg-type]

    app.add_middleware(FailureBoundary)

    @app.get("/health/live", include_in_schema=False)
    async def live() -> Response:
        return Response(headers={"Cache-Control": "no-store"})

    @app.get("/health/ready", include_in_schema=False)
    async def ready() -> Response:
        if services.ready:
            await services.ready()
        return Response(headers={"Cache-Control": "no-store"})

    document = app.openapi()
    for path, methods in (
        ("/api/v1/people/search", ("get",)),
        ("/api/v1/following", ("get", "post", "delete")),
        ("/api/v1/timeline", ("get",)),
    ):
        for method in methods:
            document["paths"][path][method]["responses"].pop("422", None)
    app.openapi_schema = document
    return app


def create_runtime_app() -> FastAPI:
    from pydantic import ValidationError

    from lumiere.bootstrap import build_container
    from lumiere.config import Settings

    try:
        settings = Settings()  # type: ignore[call-arg]
        container = build_container(settings)
    except (ValidationError, ValueError):
        raise RuntimeError("runtime configuration is invalid") from None
    from lumiere.observability import instrument_http

    app = create_app(container.services)
    instrument_http(app)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        try:
            await container.startup()
            yield
        finally:
            await container.close()

    app.router.lifespan_context = lifespan
    return app
