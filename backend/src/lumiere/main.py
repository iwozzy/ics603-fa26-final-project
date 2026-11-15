import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError

from lumiere.adapters.inbound.http.deps import HttpServices
from lumiere.adapters.inbound.http.errors import failure_response, validation_failure
from lumiere.adapters.inbound.http.routers.v1.guest_session import session_router
from lumiere.adapters.inbound.http.routers.v1.people import people_router


def create_app(services: HttpServices) -> FastAPI:
    app = FastAPI(title="Lumiere", version="0.1.0")
    app.include_router(people_router(services))
    app.include_router(session_router(services))
    app.add_exception_handler(RequestValidationError, validation_failure)  # type: ignore[arg-type]

    @app.middleware("http")
    async def bounded_request(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        try:
            async with asyncio.timeout(7):
                return await call_next(request)
        except Exception:  # noqa: BLE001 — sanitize all boundary failures before server logging
            return failure_response()

    @app.get("/health/live", include_in_schema=False)
    async def live() -> Response:
        return Response(headers={"Cache-Control": "no-store"})

    @app.get("/health/ready", include_in_schema=False)
    async def ready() -> Response:
        if services.ready:
            await services.ready()
        return Response(headers={"Cache-Control": "no-store"})

    document = app.openapi()
    document["paths"]["/api/v1/people/search"]["get"]["responses"].pop("422", None)
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
    app = create_app(container.services)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        try:
            await container.startup()
            yield
        finally:
            await container.close()

    app.router.lifespan_context = lifespan
    return app
