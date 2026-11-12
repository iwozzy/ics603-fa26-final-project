import logging
from typing import Literal

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)


class SearchInput(BaseModel):
    query: str


class SearchError(BaseModel):
    code: Literal["SEARCH_FAILED"]
    message: Literal["Unable to complete search."]


class PersonResponse(BaseModel):
    name: str = Field(min_length=1)
    portrait_url: str | None
    department: str | None
    known_for: list[str] = Field(max_length=3)


class SearchResponse(BaseModel):
    results: list[PersonResponse] = Field(max_length=7)


@router.get(
    "/api/people/search",
    response_model=SearchResponse,
    tags=["people"],
    responses={500: {"model": SearchError}},
    openapi_extra={
        "parameters": [
            {
                "name": "query",
                "in": "query",
                "required": True,
                "schema": {
                    "type": "string",
                    "description": "1–100 Unicode code points after trimming",
                },
            }
        ]
    },
)
async def search_people(
    request: Request, response: Response
) -> SearchResponse | JSONResponse:
    try:
        query = SearchInput.model_validate(dict(request.query_params)).query
        people = await request.app.state.search_people.execute(query)
    except Exception as error:  # noqa: BLE001 -- final search error boundary
        logger.error("Search failed type=%s", type(error).__name__)
        return JSONResponse(
            status_code=500,
            content=SearchError(
                code="SEARCH_FAILED", message="Unable to complete search."
            ).model_dump(),
            headers={"Cache-Control": "no-store"},
        )
    response.headers["Cache-Control"] = "private, max-age=60"
    return SearchResponse(
        results=[
            PersonResponse(
                name=person.name,
                portrait_url=person.portrait_url,
                department=person.department,
                known_for=list(person.known_for),
            )
            for person in people
        ]
    )
