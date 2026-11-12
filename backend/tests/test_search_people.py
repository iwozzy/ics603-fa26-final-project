import pytest

from lumiere.application.search_people import SearchPeople
from lumiere.domain.people import PersonSummary


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class Metadata:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def search_people(self, query: str) -> list:
        self.queries.append(query)
        return []


@pytest.mark.anyio
async def test_trims_query_without_changing_unicode_or_internal_whitespace() -> None:
    metadata = Metadata()
    assert await SearchPeople(metadata).execute("  Timothée  O’Neill \n") == []
    assert metadata.queries == ["Timothée  O’Neill"]


@pytest.mark.parametrize("query", ["", " \n\t", "𠮷" * 101])
@pytest.mark.anyio
async def test_invalid_query_does_not_call_metadata(query: str) -> None:
    metadata = Metadata()
    with pytest.raises(ValueError):
        await SearchPeople(metadata).execute(query)
    assert metadata.queries == []


@pytest.mark.parametrize("query", ["𠮷", "𠮷" * 100])
@pytest.mark.anyio
async def test_unicode_code_point_boundaries(query: str) -> None:
    metadata = Metadata()
    await SearchPeople(metadata).execute(query)
    assert metadata.queries == [query]


@pytest.mark.anyio
async def test_returns_first_seven_people_in_order_without_merging_names() -> None:
    people = [PersonSummary(name="Same name", department=str(i)) for i in range(9)]

    class ManyPeople:
        async def search_people(self, query: str) -> list[PersonSummary]:
            return people

    assert await SearchPeople(ManyPeople()).execute("name") == people[:7]


@pytest.mark.anyio
async def test_metadata_failure_is_not_disguised_as_empty_success() -> None:
    class BrokenMetadata:
        async def search_people(self, query: str) -> list[PersonSummary]:
            raise RuntimeError("provider failed")

    with pytest.raises(RuntimeError, match="provider failed"):
        await SearchPeople(BrokenMetadata()).execute("name")
