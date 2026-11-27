from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from lumiere.domain.people import MAX_PROVIDER_ID

type Nonblank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class CreditDTO(BaseModel):
    model_config = ConfigDict(strict=True, hide_input_in_errors=True)

    id: Annotated[int, Field(gt=0, le=2**63 - 1)]
    credit_id: Nonblank
    title: Nonblank
    overview: str | None = None
    poster_path: object = None
    release_date: object = None
    character: str | None = None
    order: int | None = None
    department: str | None = None
    job: str | None = None


class MovieCreditsDTO(BaseModel):
    model_config = ConfigDict(strict=True, hide_input_in_errors=True)

    cast: list[CreditDTO]
    crew: list[CreditDTO]


class FilmographyDTO(BaseModel):
    model_config = ConfigDict(strict=True, hide_input_in_errors=True)

    id: Annotated[int, Field(gt=0, le=MAX_PROVIDER_ID)]
    name: Nonblank
    known_for_department: str | None = None
    movie_credits: MovieCreditsDTO
