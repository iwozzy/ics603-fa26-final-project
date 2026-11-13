from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class BoundaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ProviderRefResponse(BoundaryModel):
    provider: Literal["tmdb"]
    entity_type: Literal["person"]
    id: Annotated[str, Field(pattern=r"^[1-9][0-9]*$")]


class PersonResponse(BoundaryModel):
    provider_ref: ProviderRefResponse
    name: Annotated[str, Field(min_length=1, pattern=r"\S")]
    portrait_url: (
        Annotated[
            str,
            Field(
                pattern=r"^https://image\.tmdb\.org/t/p/w180_and_h180_face/[A-Za-z0-9_-]+\.[A-Za-z0-9]+$"
            ),
        ]
        | None
    )
    department: Annotated[str, Field(min_length=1, pattern=r"\S")] | None
    known_for: Annotated[
        list[Annotated[str, Field(min_length=1, pattern=r"\S")]], Field(max_length=3)
    ]


class SearchResponse(BoundaryModel):
    results: Annotated[list[PersonResponse], Field(max_length=7)]
