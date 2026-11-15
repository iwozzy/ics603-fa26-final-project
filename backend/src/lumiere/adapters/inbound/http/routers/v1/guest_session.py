from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response

from lumiere.adapters.inbound.http.context import (
    COOKIE_NAME,
    check_origin,
    quota_ip_key,
    transport_scheme,
)
from lumiere.adapters.inbound.http.deps import HttpServices


def session_router(services: HttpServices) -> APIRouter:
    router = APIRouter()

    @router.post("/api/v1/guest-session", operation_id="bootstrapGuestSession", response_class=Response, responses={500: {"description": "Bootstrap failed"}})
    async def bootstrap(request: Request) -> Response:
        check_origin(request, services)
        session = await services.sessions.bootstrap(request.cookies.get(COOKIE_NAME), quota_ip_key(request, services), datetime.now(UTC))
        response = Response(headers={"Cache-Control": "no-store"})
        if session.is_new:
            response.set_cookie(COOKIE_NAME, session.proof, httponly=True, secure=transport_scheme(request, services) == "https", samesite="lax", path="/")
        return response

    return router
