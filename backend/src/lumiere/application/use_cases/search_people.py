from lumiere.application.ports.catalog import PeopleCatalog
from lumiere.application.ports.clock import Clock
from lumiere.application.ports.usage import UsageAdmission
from lumiere.domain.access import GuestContext
from lumiere.domain.errors import SearchFailed
from lumiere.domain.people import SearchPeopleResult, normalize_query


class SearchPeople:
    def __init__(self, catalog: PeopleCatalog, admission: UsageAdmission, clock: Clock) -> None:
        self.catalog = catalog
        self.admission = admission
        self.clock = clock

    async def execute(self, raw_query: str, context: GuestContext) -> SearchPeopleResult:
        query = normalize_query(raw_query)
        # Admission commits a nonrefundable charge before any provider I/O.
        await self.admission.admit_and_charge(context, self.clock.now())
        try:
            candidates = await self.catalog.search_first_page(query)
        except Exception:  # noqa: BLE001 — translate provider failures; cancellation propagates
            raise SearchFailed("provider") from None
        return SearchPeopleResult(query, candidates[:7])
