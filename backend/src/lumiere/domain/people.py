from dataclasses import dataclass

from lumiere.domain.errors import SearchFailed


@dataclass(frozen=True)
class PersonSummary:
    name: str
    department: str | None
    profile_image_url: str | None
    known_for: tuple[str, ...]


@dataclass(frozen=True)
class SearchPeopleResult:
    query: str
    people: tuple[PersonSummary, ...]


def normalize_query(raw_query: str) -> str:
    query = raw_query.strip()
    if not 1 <= len(query) <= 200:
        raise SearchFailed("invalid_query")
    return query
