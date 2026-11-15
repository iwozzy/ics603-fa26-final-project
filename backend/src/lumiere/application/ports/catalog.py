from typing import Protocol

from lumiere.domain.people import PersonSummary


class PeopleCatalog(Protocol):
    async def search_first_page(self, query: str) -> tuple[PersonSummary, ...]: ...
