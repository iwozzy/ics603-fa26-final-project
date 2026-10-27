"""Request and output contracts for the future movie discovery agent."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Page inputs; the skeleton accepts them without performing a search."""

    category: Literal["cast_crew", "movies"] = "cast_crew"
    query: str = ""
    note: str = ""
    photo_data_url: str | None = None
    storyline_query: str = ""
    watch_status: Literal["unseen", "all", "seen"] = "all"


class Person(BaseModel):
    name: str
    portrait: str | None = None
    role: str
    known_for: list[str] = Field(default_factory=list)


class Movie(BaseModel):
    title: str
    poster: str | None = None
    release_year: int
    release_date: date | None = None
    tagline: str = ""
    storyline: str = ""
    genres: list[str] = Field(default_factory=list)
    runtime_minutes: int | None = None
    cast: list[Person] = Field(default_factory=list)
    crew: list[Person] = Field(default_factory=list)
    watch_status: Literal["unseen", "seen"] = "unseen"
    in_watch_list: bool = False


class SearchResponse(BaseModel):
    message: str
    people: list[Person] = Field(default_factory=list)
    movies: list[Movie] = Field(default_factory=list)
