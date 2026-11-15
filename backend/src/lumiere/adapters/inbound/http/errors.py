import asyncio

from fastapi import Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from lumiere.domain.errors import SearchFailed


def failure_response() -> Response:
    return Response(status_code=500, headers={"Cache-Control": "no-store"})


async def validation_failure(request: Request, exc: RequestValidationError) -> Response:
    if request.url.path == "/api/v1/people/search":
        return failure_response()
    return await request_validation_exception_handler(request, exc)


class FailureBoundary:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracked_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            async with asyncio.timeout(7):
                await self.app(scope, receive, tracked_send)
        except Exception as error:  # noqa: BLE001 — sanitize at the outer HTTP boundary
            category = error.category if isinstance(error, SearchFailed) else "deadline" if isinstance(error, TimeoutError) else "internal"
            scope.setdefault("state", {})["failure_category"] = category
            if not started:
                await failure_response()(scope, receive, send)
