import json

import httpx
import logfire
import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from lumiere.adapters.inbound.http.deps import HttpServices
from lumiere.adapters.outbound.clients.tmdb_people.client import TMDBPeopleCatalog
from lumiere.application.use_cases.following import (
    FollowPerson,
    ListFollowing,
    UnfollowPerson,
)
from lumiere.application.use_cases.guest_identity import GuestIdentityService
from lumiere.application.use_cases.search_people import SearchPeople
from lumiere.domain.access import UsagePolicy
from lumiere.domain.errors import SearchFailed
from lumiere.main import create_app
from tests.fakes.access import MemoryAccess
from tests.fakes.following import MemoryFollowing
from tests.fakes.hydration import RecordingFilmographyQueue
from tests.fakes.search import FakeAdmission, FakeClock, FakePeopleQueue


async def test_sanitized_correlated_boundary_spans(monkeypatch: pytest.MonkeyPatch) -> None:
    import lumiere.observability as telemetry

    exporter = InMemorySpanExporter()
    logfire.configure(send_to_logfire=False, console=False, inspect_arguments=False, add_baggage_to_attributes=False, additional_span_processors=[SimpleSpanProcessor(exporter)])
    monkeypatch.setattr(telemetry, "_configure_export", lambda: True)
    telemetry.configure_observability(True)
    admission = FakeAdmission()
    async with httpx.AsyncClient(base_url="https://provider.test", transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"results": [{"id": 1, "name": "SENTINEL_PAYLOAD"}, {"id": False, "name": "invalid"}]}))) as provider:
        catalog = TMDBPeopleCatalog(provider, report=telemetry.record_catalog_counts)
        policy = UsagePolicy(100,100,100,100,100,100,100,100,100,100)
        services = HttpServices(SearchPeople(catalog, admission, FakeClock(), FakePeopleQueue()), GuestIdentityService(MemoryAccess(), policy), b"synthetic-key", list_following=ListFollowing(MemoryFollowing()), follow_person=FollowPerson(MemoryFollowing(), RecordingFilmographyQueue()), unfollow_person=UnfollowPerson(MemoryFollowing()))
        app = create_app(telemetry.observe_services(services))
        telemetry.instrument_http(app)
        async with httpx.AsyncClient(base_url="https://app.test", transport=httpx.ASGITransport(app=app)) as client:
            await client.post("/api/v1/guest-session")
            response = await client.get("/api/v1/people/search?query=SENTINEL_QUERY", headers={"Authorization": "SENTINEL_AUTH", "X-Correlation-ID": "SENTINEL_CORRELATION"})
            assert response.status_code == 200
            admission.error = SearchFailed("quota")
            assert (await client.get("/api/v1/people/search?query=SENTINEL_QUERY")).status_code == 500
    spans = exporter.get_finished_spans()
    serialized = json.dumps([dict(span.attributes or {}) for span in spans])
    for sentinel in ("SENTINEL_QUERY", "SENTINEL_PAYLOAD", "SENTINEL_AUTH", "SENTINEL_CORRELATION"):
        assert sentinel not in serialized
    attributes = [dict(span.attributes or {}) for span in spans]
    assert any(item.get("selected_count") == 1 for item in attributes)
    assert any(item.get("invalid_count") == 1 for item in attributes)
    assert any(item.get("quota_outcome") == "rejected" for item in attributes)
    assert any(item.get("failure_category") == "quota" for item in attributes)
    assert all(span.end_time is not None and span.start_time is not None and span.end_time >= span.start_time for span in spans)
    trace_ids = [span.context.trace_id for span in spans if span.context is not None and span.name in ("http.search", "people.search")]
    assert len(trace_ids) >= 4 and len(set(trace_ids)) < len(trace_ids)
    telemetry.configure_observability(False)


@pytest.mark.parametrize("fails", [False, True])
def test_database_spans_capture_sql_without_parameters_or_connection(monkeypatch: pytest.MonkeyPatch, fails: bool) -> None:
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError

    import lumiere.observability as telemetry

    exporter = InMemorySpanExporter()
    logfire.configure(send_to_logfire=False, console=False, inspect_arguments=False, additional_span_processors=[SimpleSpanProcessor(exporter)])
    monkeypatch.setattr(telemetry, "_configure_export", lambda: True)
    telemetry.configure_observability(True)
    engine = create_engine("sqlite:///:memory:", hide_parameters=True)
    telemetry.instrument_database(engine)
    statement = "SELECT :value FROM missing_table" if fails else "SELECT :value"
    with engine.connect() as connection:
        if fails:
            with pytest.raises(OperationalError):
                connection.scalar(text(statement), {"value": "SENTINEL_SQL"})
        else:
            assert connection.scalar(text(statement), {"value": "SENTINEL_SQL"}) == "SENTINEL_SQL"
    spans = exporter.get_finished_spans()
    serialized = json.dumps([dict(span.attributes or {}) for span in spans])
    expected_sql = "SELECT ? FROM missing_table" if fails else "SELECT ?"
    assert any(span.name == "database.query" and (span.attributes or {}).get("db.query.text") == expected_sql for span in spans)
    assert "SENTINEL_SQL" not in serialized and "sqlite:" not in serialized
    engine.dispose()
    telemetry.configure_observability(False)


async def test_telemetry_failure_does_not_block_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    import lumiere.observability as telemetry

    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("synthetic exporter outage")

    monkeypatch.setattr(telemetry, "_configure_export", lambda: True)
    telemetry.configure_observability(True)
    monkeypatch.setattr(logfire, "span", broken)
    async with httpx.AsyncClient(transport=telemetry.ObservedTransport(httpx.MockTransport(lambda _: httpx.Response(200)))) as client:
        assert (await client.get("https://provider.test/?query=SENTINEL_QUERY")).status_code == 200
    telemetry.configure_observability(False)


def test_people_events_are_sanitized_and_reporter_outage_is_contained(monkeypatch: pytest.MonkeyPatch) -> None:
    import lumiere.observability as telemetry
    from lumiere.application.ports.people import PeopleWriteEvent
    exporter = InMemorySpanExporter()
    logfire.configure(send_to_logfire=False, console=False, inspect_arguments=False, additional_span_processors=[SimpleSpanProcessor(exporter)])
    monkeypatch.setattr(telemetry, '_configure_export', lambda: True)
    telemetry.configure_observability(True)
    telemetry.record_people_write(PeopleWriteEvent('retry', 4, 2, 1, 17))
    attributes = [dict(span.attributes or {}) for span in exporter.get_finished_spans() if span.name == 'people.persistence']
    assert any(item.get('event_kind') == 'retry' and item.get('outstanding') == 4 and item.get('in_flight') == 2 and item.get('attempt') == 1 and item.get('duration_ms') == 17 for item in attributes)
    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError('SENTINEL_EXCEPTION')
    monkeypatch.setattr(logfire, 'span', broken)
    telemetry.record_people_write(PeopleWriteEvent('failed', 0, 0))
    assert 'SENTINEL' not in json.dumps(attributes)
    telemetry.configure_observability(False)


@pytest.mark.parametrize('category', ['missing_person', 'follow_limit', 'invalid_identity', 'session', 'storage', 'deadline'])
async def test_follow_spans_sanitize_identity_and_errors(monkeypatch: pytest.MonkeyPatch, category: str) -> None:
    from uuid import uuid4

    import lumiere.observability as telemetry
    from lumiere.domain.access import GuestContext
    from lumiere.domain.errors import FollowingFailed
    from lumiere.domain.following import FollowingSnapshot, PersonIdentity
    from lumiere.domain.people import CatalogProvider
    from tests.fakes.search import sample_person

    exporter = InMemorySpanExporter()
    logfire.configure(send_to_logfire=False, console=False, inspect_arguments=False, additional_span_processors=[SimpleSpanProcessor(exporter)])
    monkeypatch.setattr(telemetry, '_configure_export', lambda: True)
    telemetry.configure_observability(True)
    class Follow:
        async def execute(self, identity: PersonIdentity, context: GuestContext) -> FollowingSnapshot:
            raise FollowingFailed(category)
    class Unfollow:
        async def execute(self, identity: PersonIdentity, context: GuestContext) -> None:
            raise FollowingFailed(category)
    class List:
        async def execute(self, context: GuestContext) -> FollowingSnapshot:
            return FollowingSnapshot((sample_person(4139, name='SENTINEL_PERSON'),), 3)
    try:
        context = GuestContext(uuid4(), 'SENTINEL_IP')
        with pytest.raises(FollowingFailed):
            await telemetry.ObservedFollowPerson(Follow()).execute(PersonIdentity(CatalogProvider.TMDB, 4139), context)
        with pytest.raises(FollowingFailed):
            await telemetry.ObservedUnfollowPerson(Unfollow()).execute(PersonIdentity(CatalogProvider.TMDB, 4139), context)
        await telemetry.ObservedListFollowing(List()).execute(context)
        spans = exporter.get_finished_spans()
        assert {s.name for s in spans} >= {'following.list', 'following.follow', 'following.unfollow'}
        attributes = [dict(s.attributes or {}) for s in spans]
        assert any(a.get('failure_category') == category for a in attributes)
        encoded = json.dumps(attributes)
        assert 'SENTINEL' not in encoded and '4139' not in encoded and str(context.profile_id) not in encoded
    finally:
        telemetry.configure_observability(False)


@pytest.mark.parametrize('category', [
    'provider_throttled', 'provider_status', 'provider_transport', 'provider_response',
    'provider_oversize', 'provider_identity_mismatch', 'provider_credit_conflict', 'SENTINEL_EXCEPTION',
])
async def test_hydration_telemetry_sanitizes_events_and_fetch_failures(
    monkeypatch: pytest.MonkeyPatch, category: str,
) -> None:
    from uuid import uuid4

    import lumiere.observability as telemetry
    from lumiere.application.ports.filmography import HydrationEvent
    from lumiere.application.provider_dispatch import ProviderDispatch
    from lumiere.domain.access import GuestContext
    from lumiere.domain.errors import HydrationFailed, HydrationThrottled
    from lumiere.domain.following import PersonIdentity
    from lumiere.domain.people import CatalogProvider
    from tests.fakes.hydration import (
        ControlledFilmography,
        ControlledFilmographyCatalog,
        ControlledHydrationClock,
        RecordingAdmission,
    )

    exporter = InMemorySpanExporter()
    logfire.configure(send_to_logfire=False, console=False, inspect_arguments=False, additional_span_processors=[SimpleSpanProcessor(exporter)])
    monkeypatch.setattr(telemetry, '_configure_export', lambda: True)
    telemetry.configure_observability(True)
    clock = ControlledHydrationClock()
    catalog = ControlledFilmographyCatalog()
    catalog.errors.append(HydrationThrottled(120) if category == 'provider_throttled' else HydrationFailed(category))
    observed_catalog = telemetry.ObservedFilmographyCatalog(catalog)
    admission = RecordingAdmission()
    admission.reject = True
    hydrate = telemetry.ObservedHydrateFilmography(ControlledFilmography(clock), observed_catalog, ProviderDispatch(admission, clock), clock)
    identity = PersonIdentity(CatalogProvider.TMDB, 4139)
    context = GuestContext(uuid4(), 'SENTINEL_IP')
    try:
        telemetry.record_hydration(HydrationEvent('accepted', 4, 2, 0, 17))
        with pytest.raises(HydrationFailed):
            await observed_catalog.fetch(identity)
        with pytest.raises(SearchFailed, match='quota'):
            await hydrate.execute(identity, context)
        attributes = {s.name: dict(s.attributes or {}) for s in exporter.get_finished_spans()}
        expected_queue = {'event_kind': 'accepted', 'outstanding': 4, 'in_flight': 2, 'attempt': 0, 'duration_ms': 17}
        assert expected_queue.items() <= attributes['filmography.queue'].items()
        assert attributes['filmography.provider']['failure_category'] == ('internal' if category.startswith('SENTINEL') else category)
        assert attributes['filmography.hydrate']['quota_outcome'] == 'rejected'
        assert attributes['filmography.hydrate']['failure_category'] == 'quota'
        encoded = json.dumps(attributes)
        assert 'SENTINEL' not in encoded and '4139' not in encoded and str(context.profile_id) not in encoded
    finally:
        telemetry.configure_observability(False)
