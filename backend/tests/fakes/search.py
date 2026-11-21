from datetime import UTC, datetime

from lumiere.domain.access import GuestContext
from lumiere.domain.people import CatalogProvider, PersonSummary


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


def sample_person(provider_id: int = 4139, *, name: str = "Tom", known_for_department: str | None = None, profile_image_url: str | None = None, known_for: tuple[str, ...] = (), provider_profile_path: str | None = None) -> PersonSummary:
    return PersonSummary(provider=CatalogProvider.TMDB, provider_id=provider_id, name=name, known_for_department=known_for_department, profile_image_url=profile_image_url, known_for=known_for, provider_profile_path=provider_profile_path)
