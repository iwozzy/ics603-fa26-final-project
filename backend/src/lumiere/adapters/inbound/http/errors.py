from fastapi import Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError


def failure_response() -> Response:
    return Response(status_code=500, headers={"Cache-Control": "no-store"})


async def validation_failure(request: Request, exc: RequestValidationError) -> Response:
    if request.url.path == "/api/v1/people/search":
        return failure_response()
    return await request_validation_exception_handler(request, exc)
