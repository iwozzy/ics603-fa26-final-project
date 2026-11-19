"""Transient application search capability; no framework or provider dependencies."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import Protocol


class SearchUnavailable(Exception):
    pass


@dataclass(frozen=True)
class ProviderRef:
    provider: str
    entity_type: str
    id: str


@dataclass(frozen=True)
class SearchPerson:
    provider_ref: ProviderRef
    name: str
    portrait_url: str | None
    department: str | None
    known_for: tuple[str, ...]


class PeopleProvider(Protocol):
    """Supply usable first-page candidates in provider order."""

    async def search_people(self, name: str) -> list[SearchPerson]: ...


class Admission(Protocol):
    def acquire(self) -> bool: ...
    def release(self) -> None: ...


type SearchOperation = Callable[[str], Awaitable[list[SearchPerson]]]


def normalize_search_name(name: str, max_query_chars: int) -> str:
    name = name.strip()
    if not name or len(name) > max_query_chars:
        raise SearchUnavailable()
    return name


async def search_people(
    name: str, provider: PeopleProvider, max_query_chars: int
) -> list[SearchPerson]:
    candidates = await provider.search_people(
        normalize_search_name(name, max_query_chars)
    )
    results = []
    seen: set[ProviderRef] = set()
    for person in candidates:
        if person.provider_ref in seen:
            continue
        seen.add(person.provider_ref)
        results.append(replace(person, known_for=person.known_for[:3]))
        if len(results) == 7:
            break
    return results
