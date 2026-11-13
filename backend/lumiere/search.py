"""Transient application search capability; no framework or provider dependencies."""

from dataclasses import dataclass
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
    async def search_people(self, name: str) -> list[SearchPerson]: ...


class Admission(Protocol):
    def acquire(self) -> bool: ...
    def release(self) -> None: ...


async def search_people(name: str, provider: PeopleProvider) -> list[SearchPerson]:
    return await provider.search_people(name)
