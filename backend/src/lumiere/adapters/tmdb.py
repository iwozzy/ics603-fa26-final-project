import asyncio
import logging
import re
from contextlib import nullcontext
from time import perf_counter
from typing import Annotated, Literal

import httpx
import logfire
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
)

from lumiere.application.search_people import SearchFailed
from lumiere.domain.people import PersonSummary

logger = logging.getLogger(__name__)
IMAGE_BASE = "https://image.tmdb.org/t/p/w180_and_h180_face"


class Envelope(BaseModel):
    results: list[object]


class Hint(BaseModel):
    media_type: Literal["movie", "tv"]
    title: object = None
    name: object = None


def optional_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    logger.warning("Malformed optional display text")
    return None


def normalize_titles(value: object) -> list[str]:
    if not isinstance(value, list):
        logger.warning("Malformed known-for list")
        return []
    titles = []
    for item in value:
        try:
            hint = Hint.model_validate(item)
        except ValidationError:
            logger.warning("Malformed or unsupported known-for entry")
            continue
        title = optional_text(hint.title if hint.media_type == "movie" else hint.name)
        if title:
            titles.append(title)
    return titles[:3]


class Person(BaseModel):
    model_config = ConfigDict(strict=True)
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    profile_path: str | None = None
    known_for_department: str | None = None
    known_for: list[str] = Field(default_factory=list)

    @field_validator("known_for_department", mode="before")
    @classmethod
    def department(cls, value: object) -> str | None:
        return optional_text(value)

    @field_validator("profile_path", mode="before")
    @classmethod
    def profile(cls, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str) and re.fullmatch(
            r"/[A-Za-z0-9_-]+\.(?:jpg|jpeg|png|webp)", value
        ):
            return value
        logger.warning("Malformed portrait path")
        return None

    @field_validator("known_for", mode="before")
    @classmethod
    def titles(cls, value: object) -> list[str]:
        return normalize_titles(value)


def normalize_people(envelope: Envelope) -> tuple[list[PersonSummary], int]:
    people = []
    skipped = 0
    for value in envelope.results:
        try:
            person = Person.model_validate(value)
        except ValidationError:
            logger.warning("Skipped malformed person")
            skipped += 1
            continue
        people.append(
            PersonSummary(
                name=person.name,
                department=person.known_for_department,
                portrait_url=IMAGE_BASE + person.profile_path
                if person.profile_path
                else None,
                known_for=tuple(person.known_for),
            )
        )
        if len(people) == 7:
            break
    return people, skipped


class TMDBSearch:
    def __init__(
        self,
        client: httpx.AsyncClient,
        token: str,
        telemetry: logfire.Logfire | None = None,
    ) -> None:
        self.client = client
        self.token = token
        self.telemetry = telemetry

    async def search_people(self, query: str) -> list[PersonSummary]:
        context = (
            self.telemetry.span(
                "TMDB people search",
                outcome="failure",
                skipped_records=0,
                result_count=0,
            )
            if self.telemetry
            else nullcontext()
        )
        start = perf_counter()
        with context as span:
            try:
                people, skipped = await self._fetch(query)
                if span:
                    span.set_attribute("skipped_records", skipped)
                    span.set_attribute("result_count", len(people))
                if skipped and not people:
                    raise SearchFailed()
                if span:
                    span.set_attribute("outcome", "success")
                return people
            except SearchFailed:
                logger.error("Provider search failed")
                raise
            finally:
                if span:
                    span.set_attribute(
                        "duration_ms", round((perf_counter() - start) * 1000, 2)
                    )

    async def _fetch(self, query: str) -> tuple[list[PersonSummary], int]:
        try:
            async with asyncio.timeout(10):
                response = await self.client.get(
                    "https://api.themoviedb.org/3/search/person",
                    params={"query": query, "page": 1},
                    headers={"Authorization": f"Bearer {self.token}"},
                )
                response.raise_for_status()
                envelope = Envelope.model_validate(response.json())
                return normalize_people(envelope)
        except (httpx.HTTPError, TimeoutError, ValidationError, ValueError):
            raise SearchFailed() from None
