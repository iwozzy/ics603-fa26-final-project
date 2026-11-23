from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from lumiere.adapters.inbound.http.schemas.people import PersonResponse
from lumiere.domain.people import MAX_PROVIDER_ID, CatalogProvider


class FollowPersonRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    provider: CatalogProvider
    provider_id: Annotated[int, Field(strict=True, gt=0, le=MAX_PROVIDER_ID)]


class FollowingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, hide_input_in_errors=True)
    people: Annotated[list[PersonResponse], Field(max_length=3)]
    limit: Literal[3]
