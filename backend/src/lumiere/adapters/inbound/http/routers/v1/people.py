from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from lumiere.adapters.inbound.http.context import COOKIE_NAME, quota_ip_key
from lumiere.adapters.inbound.http.deps import HttpServices
from lumiere.adapters.inbound.http.schemas.people import SearchPeopleResponse
from lumiere.domain.people import SearchPeopleResult, normalize_query


def people_router(services: HttpServices) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/people/search", operation_id="searchPeople", response_model=SearchPeopleResponse, responses={500: {"description": "Search failed"}})
    async def search(request: Request, response: Response, query: Annotated[str, Query()]) -> SearchPeopleResult:
        normalized = normalize_query(query)
        context = await services.guests.resolve(request.cookies.get(COOKIE_NAME), quota_ip_key(request, services), datetime.now(UTC))
        result = await services.search_people.execute(normalized, context)
        response.headers["Cache-Control"] = f"private, max-age={services.search_cache_max_age_seconds}"
        return result

    return router
