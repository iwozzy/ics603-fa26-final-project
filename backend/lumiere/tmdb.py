import asyncio
import re
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from .config import Settings
from .search import Admission, ProviderRef, SearchPerson, SearchUnavailable

PORTRAIT_BASE = "https://image.tmdb.org/t/p/w180_and_h180_face/"


class SearchEnvelope(BaseModel):
    model_config = ConfigDict(strict=True)
    results: list[Any]


class PersonPayload(BaseModel):
    model_config = ConfigDict(strict=True)
    id: int
    name: str
    # Optional metadata is independently checked; bad metadata never hides a person.
    profile_path: Any = None
    known_for_department: Any = None
    known_for: Any = None


def nonblank(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _recognition_titles(known_for: Any) -> tuple[str, ...]:
    if not isinstance(known_for, list):
        return ()
    titles = []
    for credit in known_for:
        if not isinstance(credit, dict):
            continue
        field = {"movie": "title", "tv": "name"}.get(str(credit.get("media_type")))
        label = nonblank(credit.get(field)) if field else None
        if label:
            titles.append(label)
        if len(titles) == 3:
            break
    return tuple(titles)


def normalize(payload: Any) -> list[SearchPerson]:
    envelope = SearchEnvelope.model_validate(payload)
    people = []
    seen = set()
    for raw in envelope.results:
        try:
            row = PersonPayload.model_validate(raw)
        except ValidationError:
            continue
        name = nonblank(row.name)
        if row.id <= 0 or not name or row.id in seen:
            continue
        seen.add(row.id)
        path = nonblank(row.profile_path)
        portrait = None
        if path and re.fullmatch(
            r"/+[A-Za-z0-9_-]+\.(?:jpg|jpeg|png|webp)", path, re.IGNORECASE
        ):
            portrait = PORTRAIT_BASE + path.lstrip("/")
        people.append(
            SearchPerson(
                ProviderRef("tmdb", "person", str(row.id)),
                name,
                portrait,
                nonblank(row.known_for_department),
                _recognition_titles(row.known_for),
            )
        )
        if len(people) == 7:
            break
    return people


class TmdbPeople:
    def __init__(
        self, client: httpx.AsyncClient, settings: Settings, admission: Admission
    ):
        self.client = client
        self.settings = settings
        self.admission = admission

    async def search_people(self, name: str) -> list[SearchPerson]:
        if not self.settings.tmdb_token or not self.admission.acquire():
            raise SearchUnavailable()
        try:
            async with asyncio.timeout(self.settings.provider_timeout):
                async with self.client.stream(
                    "GET",
                    "https://api.themoviedb.org/3/search/person",
                    params={"query": name, "page": 1},
                    headers={"Authorization": f"Bearer {self.settings.tmdb_token}"},
                    timeout=self.settings.provider_timeout,
                ) as response:
                    response.raise_for_status()
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > self.settings.max_provider_bytes:
                            raise SearchUnavailable()
                    return normalize(
                        SearchEnvelope.model_validate_json(data).model_dump()
                    )
        except (httpx.HTTPError, TimeoutError, ValidationError, ValueError):
            raise SearchUnavailable() from None
        finally:
            self.admission.release()
