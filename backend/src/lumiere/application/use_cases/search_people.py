import asyncio

from lumiere.application.ports.catalog import PeopleCatalog
from lumiere.application.ports.clock import Clock
from lumiere.application.ports.usage import UsageAdmission
from lumiere.domain.access import AttemptOutcome, GuestContext
from lumiere.domain.errors import SearchFailed
from lumiere.domain.people import SearchPeopleResult, normalize_query


class SearchPeople:
    def __init__(self, catalog: PeopleCatalog, admission: UsageAdmission, clock: Clock) -> None:
        self.catalog = catalog
        self.admission = admission
        self.clock = clock

    async def execute(self, raw_query: str, context: GuestContext) -> SearchPeopleResult:
        query = normalize_query(raw_query)
        reservation = await self.admission.admit(context, self.clock.now())
        # Mark durably before I/O. An ambiguous mark must never refund capacity.
        await self.admission.mark_dispatched(reservation)
        try:
            candidates = await self.catalog.search_first_page(query)
        except asyncio.CancelledError:
            await asyncio.shield(self.admission.finish(reservation, AttemptOutcome.CANCELLED))
            raise
        except Exception:  # noqa: BLE001 — settle any unexpected provider failure
            await self.admission.finish(reservation, AttemptOutcome.FAILED)
            raise SearchFailed("provider") from None
        await self.admission.finish(reservation, AttemptOutcome.SUCCESS)
        return SearchPeopleResult(query, candidates[:7])
