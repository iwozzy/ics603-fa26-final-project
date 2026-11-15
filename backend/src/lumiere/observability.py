"""Explicit boundary spans. No request URLs, content, SQL text, or exceptions."""
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from tempfile import TemporaryDirectory
from typing import Any, override
from uuid import uuid4

import httpx
import logfire
from fastapi import FastAPI
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy import Connection, Engine, event
from sqlalchemy.engine import ExceptionContext, ExecutionContext
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from lumiere.adapters.inbound.http.deps import HttpServices
from lumiere.application.ports.search import PeopleSearch
from lumiere.domain.access import GuestContext
from lumiere.domain.errors import SearchFailed
from lumiere.domain.people import SearchPeopleResult

_enabled = False
_ALLOWED = {"selected_count", "invalid_count", "failure_category", "quota_outcome", "status_code", "correlation_id"}
_CATEGORIES = {"invalid_query", "quota", "bootstrap_quota", "session", "storage", "provider", "provider_response", "provider_oversize", "deadline", "cancelled"}


def _configure_export() -> bool:
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return False
    # SDK config/data paths are fresh and empty; never discover local credentials.
    with TemporaryDirectory(prefix="lumiere-telemetry-") as directory:
        logfire.configure(send_to_logfire=False, console=False, service_name="Lumiere", config_dir=directory, data_dir=directory, inspect_arguments=False, add_baggage_to_attributes=False, metrics=False, distributed_tracing=False, additional_span_processors=[BatchSpanProcessor(OTLPSpanExporter())])
    return True


def configure_observability(enabled: bool) -> None:
    global _enabled
    _enabled = False
    if enabled:
        try:
            _enabled = _configure_export()
        except Exception:  # noqa: BLE001, S110 — diagnostics cannot block the application
            pass


@contextmanager
def safe_span(name: str) -> Iterator[dict[str, str | int]]:
    span = None
    attributes: dict[str, str | int] = {}
    if _enabled:
        try:
            span = logfire.span(name)
            span.__enter__()
        except Exception:  # noqa: BLE001
            span = None
    try:
        yield attributes
    finally:
        if span is not None:
            try:
                for key, value in attributes.items():
                    if key in _ALLOWED:
                        span.set_attribute(key, value)
                # Never pass an exception to the SDK's context manager.
                span.__exit__(None, None, None)
            except Exception:  # noqa: BLE001, S110 — never log exporter errors
                pass


def record_catalog_counts(selected: int, invalid: int) -> None:
    with safe_span("catalog.page") as attributes:
        attributes.update(selected_count=selected, invalid_count=invalid)


class ObservedSearch:
    def __init__(self, inner: PeopleSearch) -> None:
        self.inner = inner

    async def execute(self, raw_query: str, context: GuestContext) -> SearchPeopleResult:
        with safe_span("people.search") as attributes:
            try:
                result = await self.inner.execute(raw_query, context)
                attributes.update(selected_count=len(result.people), quota_outcome="admitted")
                return result
            except SearchFailed as error:
                category = error.category if error.category in _CATEGORIES else "internal"
                attributes.update(failure_category=category, quota_outcome="rejected" if category == "quota" else "failed")
                raise


def observe_services(services: HttpServices) -> HttpServices:
    return replace(services, search_people=ObservedSearch(services.search_people))


class HttpTelemetry:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        name = {"/api/v1/people/search": "http.search", "/api/v1/guest-session": "http.bootstrap"}.get(scope["path"], "http.other")
        with safe_span(name) as attributes:
            attributes["correlation_id"] = str(uuid4())

            async def sanitized_send(message: Message) -> None:
                if message["type"] == "http.response.start":
                    attributes["status_code"] = message["status"]
                await send(message)

            await self.app(scope, receive, sanitized_send)
            category = scope.get("state", {}).get("failure_category")
            if category:
                attributes["failure_category"] = category if category in _CATEGORIES else "internal"


def instrument_http(app: FastAPI) -> None:
    app.add_middleware(HttpTelemetry)


class ObservedTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
        self.inner = inner

    @override
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        with safe_span("catalog.http") as attributes:
            try:
                response = await self.inner.handle_async_request(request)
                attributes["status_code"] = response.status_code
                return response
            except httpx.HTTPError:
                attributes["failure_category"] = "provider"
                raise

    @override
    async def aclose(self) -> None:
        await self.inner.aclose()


def instrument_database(engine: Engine) -> None:
    spans: dict[int, Any] = {}

    def before(connection: Connection, cursor: object, statement: str, parameters: object, context: ExecutionContext, executemany: bool) -> None:
        manager = safe_span("database.query")
        manager.__enter__()
        spans[id(context)] = manager

    def after(connection: Connection, cursor: object, statement: str, parameters: object, context: ExecutionContext, executemany: bool) -> None:
        manager = spans.pop(id(context), None)
        if manager is not None:
            manager.__exit__(None, None, None)

    def failed(context: ExceptionContext) -> None:
        manager = spans.pop(id(context.execution_context), None)
        if manager is not None:
            manager.__exit__(None, None, None)

    event.listen(engine, "before_cursor_execute", before)
    event.listen(engine, "after_cursor_execute", after)
    event.listen(engine, "handle_error", failed)
