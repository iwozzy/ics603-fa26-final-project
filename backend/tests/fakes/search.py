import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from lumiere.domain.access import AttemptOutcome, GuestContext, Reservation
from lumiere.domain.people import PersonSummary


class FakeClock:
    def now(self) -> datetime:
        return datetime(2026, 11, 15, tzinfo=UTC)


class FakeCatalog:
    def __init__(self, people: tuple[PersonSummary, ...] = (), error: BaseException | None = None) -> None:
        self.people = people
        self.error = error
        self.queries: list[str] = []

    async def search_first_page(self, query: str) -> tuple[PersonSummary, ...]:
        self.queries.append(query)
        if self.error:
            raise self.error
        return self.people


class FakeAdmission:
    def __init__(self, error: Exception | None = None, mark_error: BaseException | None = None) -> None:
        self.error = error
        self.mark_error = mark_error
        self.admissions = 0
        self.dispatch_count = 0
        self.releases = 0
        self.outcomes: list[AttemptOutcome] = []
        self.finished = asyncio.Event()

    async def admit(self, context: GuestContext, now: datetime) -> Reservation:
        if self.error:
            raise self.error
        self.admissions += 1
        return Reservation(uuid4())

    async def mark_dispatched(self, reservation: Reservation) -> None:
        if self.mark_error:
            raise self.mark_error
        self.dispatch_count += 1

    async def finish(self, reservation: Reservation, outcome: AttemptOutcome) -> None:
        self.outcomes.append(outcome)
        self.finished.set()

    async def release_undispatched(self, reservation: Reservation) -> None:
        self.releases += 1
