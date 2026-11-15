import asyncio

from lumiere.application.ports.catalog import PeopleCatalog
from lumiere.application.ports.clock import Clock
from lumiere.application.ports.usage import UsageAdmission
from lumiere.domain.access import AttemptOutcome, GuestContext, Reservation
from lumiere.domain.errors import SearchFailed
from lumiere.domain.people import SearchPeopleResult, normalize_query


class SearchPeople:
    def __init__(self, catalog: PeopleCatalog, admission: UsageAdmission, clock: Clock) -> None:
        self.catalog = catalog
        self.admission = admission
        self.clock = clock
        self._settlements: set[asyncio.Task[None]] = set()

    async def execute(self, raw_query: str, context: GuestContext) -> SearchPeopleResult:
        query = normalize_query(raw_query)
        reservation = await self.admission.admit(context, self.clock.now())
        # Mark durably before I/O. An ambiguous mark must never refund capacity.
        await self.admission.mark_dispatched(reservation)
        try:
            candidates = await self.catalog.search_first_page(query)
        except asyncio.CancelledError:
            # Capacity was durably spent before dispatch. Settlement is best effort;
            # cancellation must not wait for a stalled accounting dependency.
            task = asyncio.create_task(self._settle_cancelled(reservation))
            self._settlements.add(task)
            task.add_done_callback(self._settlements.discard)
            raise
        except Exception:  # noqa: BLE001 — settle any unexpected provider failure
            await self.admission.finish(reservation, AttemptOutcome.FAILED)
            raise SearchFailed("provider") from None
        await self.admission.finish(reservation, AttemptOutcome.SUCCESS)
        return SearchPeopleResult(query, candidates[:7])

    async def _settle_cancelled(self, reservation: Reservation) -> None:
        try:
            async with asyncio.timeout(2):
                await self.admission.finish(reservation, AttemptOutcome.CANCELLED)
        except (Exception, asyncio.CancelledError):  # noqa: BLE001, S110 — keep the durable charge on uncertain settlement
            pass
