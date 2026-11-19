from datetime import UTC, datetime

from lumiere.domain.access import GuestContext
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
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.admissions = 0

    async def admit_and_charge(self, context: GuestContext, now: datetime) -> None:
        if self.error:
            raise self.error
        self.admissions += 1
