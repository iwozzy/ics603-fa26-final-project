from dataclasses import dataclass
from enum import StrEnum

from lumiere.domain.errors import SearchFailed

MAX_PROVIDER_ID = 2**53 - 1


class CatalogProvider(StrEnum):
    TMDB = "tmdb"


@dataclass(frozen=True)
class PersonSummary:
    provider: CatalogProvider
    provider_id: int
    name: str
    known_for_department: str | None
    profile_image_url: str | None
    known_for: tuple[str, ...]
    provider_profile_path: str | None = None


@dataclass(frozen=True)
class SearchPeopleResult:
    query: str
    people: tuple[PersonSummary, ...]


def normalize_query(raw_query: str) -> str:
    query = raw_query.strip()
    if not 1 <= len(query) <= 200:
        raise SearchFailed("invalid_query")
    return query
