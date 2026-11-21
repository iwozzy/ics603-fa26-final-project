import asyncio
from uuid import uuid4

import pytest

from lumiere.application.use_cases.search_people import SearchPeople
from lumiere.domain.access import GuestContext
from lumiere.domain.errors import SearchFailed
from tests.fakes.search import FakeAdmission, FakeCatalog, FakeClock, sample_person


@pytest.fixture
def context() -> GuestContext:
    return GuestContext(uuid4(), "synthetic-ip")


async def test_preserves_provider_order_and_limits_to_seven(context: GuestContext) -> None:
    catalog = FakeCatalog(tuple(sample_person(i + 1, name=str(i)) for i in range(10)))
    admission = FakeAdmission()
    result = await SearchPeople(catalog, admission, FakeClock()).execute(" Tom ", context)
    assert result.query == "Tom"
    assert [p.name for p in result.people] == [str(i) for i in range(7)]
    assert catalog.queries == ["Tom"]
    assert admission.admissions == 1


@pytest.mark.parametrize("count", [0, 3])
async def test_short_or_empty_page_never_fetches_more(context: GuestContext, count: int) -> None:
    people = tuple(sample_person(i + 1, name=str(i)) for i in range(count))
    catalog = FakeCatalog(people)
    result = await SearchPeople(catalog, FakeAdmission(), FakeClock()).execute("Tom", context)
    assert result.people == people
    assert catalog.queries == ["Tom"]


@pytest.mark.parametrize("raw", ["", "  ", "😀" * 201])
async def test_invalid_query_never_dispatches(context: GuestContext, raw: str) -> None:
    catalog, admission = FakeCatalog(), FakeAdmission()
    with pytest.raises(SearchFailed, match="invalid_query"):
        await SearchPeople(catalog, admission, FakeClock()).execute(raw, context)
    assert catalog.queries == []
    assert admission.admissions == 0


async def test_admission_failure_never_dispatches(context: GuestContext) -> None:
    catalog = FakeCatalog()
    with pytest.raises(SearchFailed, match="quota"):
        await SearchPeople(catalog, FakeAdmission(SearchFailed("quota")), FakeClock()).execute("Tom", context)
    assert catalog.queries == []


@pytest.mark.parametrize("error", [SearchFailed("provider"), asyncio.CancelledError()])
async def test_failure_or_cancellation_keeps_spent_allowance(context: GuestContext, error: BaseException) -> None:
    catalog, admission = FakeCatalog(error=error), FakeAdmission()
    with pytest.raises(type(error)):
        await SearchPeople(catalog, admission, FakeClock()).execute("Tom", context)
    assert catalog.queries == ["Tom"]
    assert admission.admissions == 1
