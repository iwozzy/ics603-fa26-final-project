import asyncio

from fastapi import Request, Response
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from lumiere.domain.errors import FollowingFailed, SearchFailed


def failure_response() -> Response:
    return Response(status_code=500, headers={"Cache-Control": "no-store"})


async def validation_failure(request: Request, exc: RequestValidationError) -> Response:
    if request.url.path == "/api/v1/following":
        request.state.failure_category = "invalid_identity"
        return failure_response()
    if request.url.path == "/api/v1/people/search":
        return failure_response()
    return await request_validation_exception_handler(request, exc)


async def http_failure(request: Request, exc: HTTPException) -> Response:
    # FastAPI raises HTTPException(400) when a JSON body cannot be decoded.
    if request.url.path == '/api/v1/following' and request.method in {'POST', 'DELETE'} and exc.status_code == 400:
        request.state.failure_category = 'invalid_identity'
        return failure_response()
    return await http_exception_handler(request, exc)


def _failure_category(error: Exception) -> str:
    if isinstance(error, (SearchFailed, FollowingFailed)):
        return error.category
    return "deadline" if isinstance(error, TimeoutError) else "internal"


class FailureBoundary:
    def __init__(self, app: ASGIApp, deadline: float = 7) -> None:
        self.app = app
        self.deadline = deadline
        self._operations: set[asyncio.Task[None]] = set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        await self._http(scope, receive, send)

    async def _http(self, scope: Scope, receive: Receive, send: Send) -> None:
        started = False
        expired = False

        async def tracked_send(message: Message) -> None:
            nonlocal started
            if expired:
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        async def invoke() -> None:
            await self.app(scope, receive, tracked_send)

        operation = asyncio.create_task(invoke())
        self._operations.add(operation)
        operation.add_done_callback(self._discard)
        try:
            # asyncio.timeout waits for cancellation cleanup. A separate wait
            # keeps dependency cleanup from extending the HTTP deadline.
            done, _ = await asyncio.wait({operation}, timeout=self.deadline)
            if not done:
                raise TimeoutError
            await operation
        except asyncio.CancelledError:
            expired = True
            operation.cancel()
            raise
        except Exception as error:  # noqa: BLE001 — sanitize at the outer HTTP boundary
            expired = True
            if operation.cancel():
                await asyncio.sleep(0)  # Deliver cancellation without waiting for cleanup.
            scope.setdefault("state", {})["failure_category"] = _failure_category(error)
            if not started:
                await failure_response()(scope, receive, send)

    def _discard(self, operation: asyncio.Task[None]) -> None:
        self._operations.discard(operation)
        if not operation.cancelled():
            operation.exception()  # Consume late errors; never log raw dependency exceptions.
