import json

import httpx
import logfire
import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from lumiere.adapters.inbound.http.deps import HttpServices
from lumiere.adapters.outbound.clients.tmdb_people.client import TMDBPeopleCatalog
from lumiere.application.use_cases.guest_identity import GuestIdentityService
from lumiere.application.use_cases.search_people import SearchPeople
from lumiere.domain.access import UsagePolicy
from lumiere.domain.errors import SearchFailed
from lumiere.main import create_app
from tests.fakes.access import MemoryAccess
from tests.fakes.search import FakeAdmission, FakeClock


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
        services = HttpServices(SearchPeople(catalog, admission, FakeClock()), GuestIdentityService(MemoryAccess(), policy), b"synthetic-key")
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


def test_database_spans_omit_sql_parameters_and_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy import create_engine, text

    import lumiere.observability as telemetry

    exporter = InMemorySpanExporter()
    logfire.configure(send_to_logfire=False, console=False, inspect_arguments=False, additional_span_processors=[SimpleSpanProcessor(exporter)])
    monkeypatch.setattr(telemetry, "_configure_export", lambda: True)
    telemetry.configure_observability(True)
    engine = create_engine("sqlite:///:memory:", hide_parameters=True)
    telemetry.instrument_database(engine)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT :value"), {"value": "SENTINEL_SQL"}) == "SENTINEL_SQL"
    spans = exporter.get_finished_spans()
    serialized = json.dumps([dict(span.attributes or {}) for span in spans])
    assert any(span.name == "database.query" for span in spans)
    assert "SENTINEL_SQL" not in serialized and "SELECT" not in serialized and "sqlite:" not in serialized
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
