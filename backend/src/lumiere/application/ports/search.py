from typing import Protocol

from lumiere.domain.access import GuestContext
from lumiere.domain.people import SearchPeopleResult


class PeopleSearch(Protocol):
    async def execute(self, raw_query: str, context: GuestContext) -> SearchPeopleResult: ...
