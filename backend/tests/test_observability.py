import logging

import httpx
import logfire
import pytest
from logfire.testing import TestExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from lumiere.bootstrap import create_app
from lumiere.config import Settings


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.parametrize(
    ("status", "results", "expected_status", "skipped"),
    [
        (200, [None, {"name": "private-provider-name"}], 200, 1),
        (503, [], 500, 0),
        (200, [None, {}], 500, 2),
    ],
)
@pytest.mark.anyio
async def test_request_provider_spans_are_correlated_and_safe(
    monkeypatch, caplog, status, results, expected_status, skipped
) -> None:
    exporter = TestExporter()
    configure = logfire.configure

    def configure_capture(**kwargs):
        return configure(
            **kwargs, additional_span_processors=[SimpleSpanProcessor(exporter)]
        )

    monkeypatch.setattr(logfire, "configure", configure_capture)
    client_type = httpx.AsyncClient

    def provider_client(**kwargs):
        return client_type(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    status,
                    json={"results": results},
                )
            ),
            **kwargs,
        )

    monkeypatch.setattr(httpx, "AsyncClient", provider_client)
    app = create_app(Settings(telemetry_enabled=False, tmdb_token="test-token"))
    with caplog.at_level(logging.INFO):
        async with (
            app.router.lifespan_context(app),
            client_type(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client,
        ):
            response = await client.get(
                "/api/people/search", params={"query": "private-query"}
            )
    assert response.status_code == expected_status
    spans = [
        span
        for span in exporter.exported_spans
        if span.attributes and span.attributes.get("logfire.span_type") == "span"
    ]
    request = next(span for span in spans if span.name == "HTTP request")
    provider = next(span for span in spans if span.name == "TMDB people search")
    assert provider.context and request.context and provider.parent
    assert provider.attributes
    assert provider.context.trace_id == request.context.trace_id
    assert provider.parent.span_id == request.context.span_id
    assert provider.attributes["outcome"] == (
        "success" if expected_status == 200 else "failure"
    )
    assert provider.attributes["skipped_records"] == skipped
    assert request.attributes and request.attributes["outcome"] == (
        "success" if expected_status == 200 else "failure"
    )
    duration = provider.attributes["duration_ms"]
    assert isinstance(duration, (int, float)) and duration >= 0
    if expected_status == 200:
        assert provider.attributes["result_count"] == 1
    exported = str(exporter.exported_spans_as_dict()) + caplog.text
    assert "private-query" not in exported
    assert "private-provider-name" not in exported
