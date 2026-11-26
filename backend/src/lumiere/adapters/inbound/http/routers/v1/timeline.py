from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from lumiere.adapters.inbound.http.context import COOKIE_NAME, quota_ip_key
from lumiere.adapters.inbound.http.deps import HttpServices
from lumiere.adapters.inbound.http.schemas.timeline import (
    TimelineQuery,
    TimelineResponse,
)


def timeline_router(services: HttpServices) -> APIRouter:
    router = APIRouter()

    @router.get(
        '/api/v1/timeline',
        operation_id='listTimeline',
        response_model=TimelineResponse,
        responses={500: {'description': 'Timeline failed'}},
    )
    async def list_timeline(
        query: Annotated[TimelineQuery, Query()], request: Request, response: Response,
    ) -> TimelineResponse:
        context = await services.guests.resolve(
            request.cookies.get(COOKIE_NAME), quota_ip_key(request, services), datetime.now(UTC),
        )
        page = await services.list_timeline.execute(query.to_request(), context)
        response.headers['Cache-Control'] = 'no-store'
        return TimelineResponse.model_validate(page)

    return router
