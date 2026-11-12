from typing import Protocol

from lumiere.domain.people import PersonSummary


class SearchFailed(Exception):
    """Discovery could not produce a valid response."""


class MetadataSearch(Protocol):
    async def search_people(self, query: str) -> list[PersonSummary]: ...


class SearchPeople:
    def __init__(self, metadata: MetadataSearch) -> None:
        self.metadata = metadata

    async def execute(self, query: str) -> list[PersonSummary]:
        query = query.strip()
        if not 1 <= len(query) <= 100:
            raise ValueError("Invalid query length")
        return (await self.metadata.search_people(query))[:7]
