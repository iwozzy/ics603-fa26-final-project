import asyncio
from uuid import uuid4

import pytest

from lumiere.application.use_cases.search_people import SearchPeople
from lumiere.domain.access import GuestContext
from lumiere.domain.errors import SearchFailed
from tests.fakes.search import (
    FakeAdmission,
    FakeCatalog,
    FakeClock,
    FakePeopleQueue,
    sample_person,
)


@pytest.fixture
def context() -> GuestContext:
    return GuestContext(uuid4(), "synthetic-ip")


async def test_preserves_provider_order_and_limits_to_seven(context: GuestContext) -> None:
    catalog = FakeCatalog(tuple(sample_person(i + 1, name=str(i)) for i in range(10)))
    admission = FakeAdmission()
    result = await SearchPeople(catalog, admission, FakeClock(), FakePeopleQueue()).execute(" Tom ", context)
    assert result.query == "Tom"
    assert [p.name for p in result.people] == [str(i) for i in range(7)]
    assert catalog.queries == ["Tom"]
    assert admission.admissions == 1


@pytest.mark.parametrize("count", [0, 3])
async def test_short_or_empty_page_never_fetches_more(context: GuestContext, count: int) -> None:
    people = tuple(sample_person(i + 1, name=str(i)) for i in range(count))
    catalog = FakeCatalog(people)
    result = await SearchPeople(catalog, FakeAdmission(), FakeClock(), FakePeopleQueue()).execute("Tom", context)
    assert result.people == people
    assert catalog.queries == ["Tom"]


@pytest.mark.parametrize("raw", ["", "  ", "😀" * 201])
async def test_invalid_query_never_dispatches(context: GuestContext, raw: str) -> None:
    catalog, admission = FakeCatalog(), FakeAdmission()
    with pytest.raises(SearchFailed, match="invalid_query"):
        await SearchPeople(catalog, admission, FakeClock(), FakePeopleQueue()).execute(raw, context)
    assert catalog.queries == []
    assert admission.admissions == 0


async def test_admission_failure_never_dispatches(context: GuestContext) -> None:
    catalog = FakeCatalog()
    with pytest.raises(SearchFailed, match="quota"):
        await SearchPeople(catalog, FakeAdmission(SearchFailed("quota")), FakeClock(), FakePeopleQueue()).execute("Tom", context)
    assert catalog.queries == []


@pytest.mark.parametrize("error", [SearchFailed("provider"), asyncio.CancelledError()])
async def test_failure_or_cancellation_keeps_spent_allowance(context: GuestContext, error: BaseException) -> None:
    catalog, admission = FakeCatalog(error=error), FakeAdmission()
    with pytest.raises(type(error)):
        await SearchPeople(catalog, admission, FakeClock(), FakePeopleQueue()).execute("Tom", context)
    assert catalog.queries == ["Tom"]
    assert admission.admissions == 1


async def test_search_returns_while_commit_is_blocked(context: GuestContext) -> None:
    from lumiere.application.people_writer import PeopleWriter
    from tests.fakes.people import ControlledPeoplePersistence
    store = ControlledPeoplePersistence()
    store.allow_commit.clear()
    writer = PeopleWriter(store, shutdown_timeout=.01)
    writer.start()
    candidates = (sample_person(2), sample_person(2)) + tuple(sample_person(i) for i in range(3, 11))
    try:
        result = await asyncio.wait_for(SearchPeople(FakeCatalog(candidates), FakeAdmission(), FakeClock(), writer).execute('Tom', context), .2)
        await asyncio.wait_for(store.committing.wait(), 1)
        assert result.people == candidates[:7]
        assert store.batches == [candidates[:7]]
        assert store.commits == 0
        store.allow_commit.set()
        await asyncio.wait_for(writer.drain(), 1)
        assert store.commits == 1
    finally:
        await writer.close()


@pytest.mark.parametrize('count', [0, 3, 9])
async def test_enqueue_only_selected_nonempty_batch(context: GuestContext, count: int) -> None:
    from tests.fakes.search import FakePeopleQueue
    people = tuple(sample_person(i + 1) for i in range(count))
    queue = FakePeopleQueue()
    result = await SearchPeople(FakeCatalog(people), FakeAdmission(), FakeClock(), queue).execute('Tom', context)
    assert queue.batches == ([people[:7]] if count else [])
    assert result.people == people[:7]


@pytest.mark.parametrize('error', [SearchFailed('provider'), asyncio.CancelledError()])
async def test_provider_failure_before_enqueue_creates_no_batch(context: GuestContext, error: BaseException) -> None:
    from tests.fakes.search import FakePeopleQueue
    queue = FakePeopleQueue()
    with pytest.raises(type(error)):
        await SearchPeople(FakeCatalog(error=error), FakeAdmission(), FakeClock(), queue).execute('Tom', context)
    assert queue.batches == []


async def test_request_cancellation_after_enqueue_leaves_write_independent(context: GuestContext) -> None:
    from lumiere.application.people_writer import PeopleWriter
    from tests.fakes.people import ControlledPeoplePersistence
    store = ControlledPeoplePersistence()
    store.allow_commit.clear()
    writer = PeopleWriter(store)
    writer.start()
    returned = asyncio.Event()
    async def request() -> None:
        await SearchPeople(FakeCatalog((sample_person(),)), FakeAdmission(), FakeClock(), writer).execute('Tom', context)
        returned.set()
        await asyncio.Event().wait()
    task = asyncio.create_task(request())
    try:
        await asyncio.wait_for(returned.wait(), 1)
        await asyncio.wait_for(store.committing.wait(), 1)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        assert len(store.active_session_tokens) == 1
        store.allow_commit.set()
        await asyncio.wait_for(writer.drain(), 1)
        assert store.commits == 1
    finally:
        task.cancel()
        store.allow_commit.set()
        await asyncio.gather(task, return_exceptions=True)
        await writer.close()


async def test_catalog_reporter_failure_keeps_search_and_enqueue(context: GuestContext) -> None:
    import httpx

    from lumiere.adapters.outbound.clients.tmdb_people.client import TMDBPeopleCatalog
    from tests.fakes.search import FakePeopleQueue
    queue = FakePeopleQueue()
    def broken(selected: int, invalid: int) -> None:
        raise RuntimeError('SENTINEL_REPORTER_DETAIL')
    async with httpx.AsyncClient(base_url='https://provider.test', transport=httpx.MockTransport(lambda _: httpx.Response(200, json={'results': [{'id': 4139, 'name': 'Tom'}]}))) as client:
        search = SearchPeople(TMDBPeopleCatalog(client, report=broken), FakeAdmission(), FakeClock(), queue)
        result = await search.execute('Tom', context)
    assert result.people[0].provider_id == 4139
    assert queue.batches == [result.people]
