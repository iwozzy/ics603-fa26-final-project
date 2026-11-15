from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Nonblank = Annotated[str, Field(min_length=1, pattern=r"\S")]


class PersonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, hide_input_in_errors=True)
    name: Nonblank
    department: str | None
    profile_image_url: str | None
    known_for: Annotated[list[Nonblank], Field(max_length=3)]


class SearchPeopleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, hide_input_in_errors=True)
    query: Annotated[str, Field(min_length=1, max_length=200)]
    people: Annotated[list[PersonResponse], Field(max_length=7)]
