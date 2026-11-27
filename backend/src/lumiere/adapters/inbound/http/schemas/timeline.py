from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from lumiere.domain.timeline import MAX_MOVIE_ID, TimelineDirection, TimelineRequest


class TimelineQuery(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)

    limit: Annotated[int, Field(ge=1, le=100)] = 20
    cursor: str | None = None
    direction: TimelineDirection | None = None
    anchor_date: date | None = None
    anchor_id: Annotated[int, Field(ge=1, le=MAX_MOVIE_ID)] | None = None

    @field_validator('limit', 'anchor_id', mode='before')
    @classmethod
    def parse_decimal_integer(cls, value: object) -> object:
        if isinstance(value, str) and not (value.isascii() and value.isdecimal()):
            raise ValueError('expected a decimal integer')
        return value

    @field_validator('anchor_date', mode='before')
    @classmethod
    def parse_calendar_date(cls, value: object) -> object:
        if isinstance(value, str) and date.fromisoformat(value).isoformat() != value:
            raise ValueError('expected a YYYY-MM-DD date')
        return value

    def to_request(self) -> TimelineRequest:
        return TimelineRequest(
            limit=self.limit,
            cursor=self.cursor,
            direction=self.direction,
            anchor_date=self.anchor_date,
            anchor_id=self.anchor_id,
        )


class MovieSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, hide_input_in_errors=True)

    id: Annotated[int, Field(strict=True, ge=1, le=MAX_MOVIE_ID)]
    title: str
    overview: str | None
    poster_image_url: str | None
    release_date: date


class TimelineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, hide_input_in_errors=True)

    items: list[MovieSummaryResponse]
    older_cursor: str | None
    newer_cursor: str | None
    as_of: date | None
    anchor_index: int | None
