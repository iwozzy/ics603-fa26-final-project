"""Explicit boundary spans. No request URLs, content, SQL parameters, or exceptions."""
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
from lumiere.adapters.inbound.http.errors import TIMELINE_FAILURE_CATEGORIES
from lumiere.application.ports.filmography import FilmographyCatalog, HydrationEvent
from lumiere.application.ports.following import (
    FollowPersonPort,
    ListFollowingPort,
    UnfollowPersonPort,
)
from lumiere.application.ports.people import PeopleWriteEvent
from lumiere.application.ports.search import PeopleSearch
from lumiere.application.ports.timeline import ListTimelinePort
from lumiere.application.use_cases.hydrate_filmography import HydrateFilmography
from lumiere.domain.access import GuestContext
from lumiere.domain.errors import (
    FollowingFailed,
    HydrationFailed,
    SearchFailed,
    TimelineFailed,
)
from lumiere.domain.filmography import PersonFilmography
from lumiere.domain.following import FollowingSnapshot, PersonIdentity
from lumiere.domain.people import SearchPeopleResult
from lumiere.domain.timeline import TimelinePage, TimelineRequest

_enabled = False
_ALLOWED = {"selected_count", "invalid_count", "failure_category", "quota_outcome", "status_code", "correlation_id", "db.query.text", "event_kind", "outstanding", "in_flight", "attempt", "duration_ms"}
_CATEGORIES = {"invalid_query", "quota", "bootstrap_quota", "session", "storage", "provider", "provider_response", "provider_oversize", "deadline", "cancelled", "missing_person", "follow_limit", "invalid_identity", "origin"} | TIMELINE_FAILURE_CATEGORIES

_HYDRATION_PROVIDER_CATEGORIES = {
    "provider_status", "provider_transport", "provider_throttled", "provider_response",
    "provider_oversize", "provider_identity_mismatch", "provider_credit_conflict",
}
_HYDRATION_EVENT_KINDS = {"accepted", "coalesced", "dropped", "started", "succeeded", "failed"}


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
    return replace(
        services,
        search_people=ObservedSearch(services.search_people),
        list_following=ObservedListFollowing(services.list_following),
        follow_person=ObservedFollowPerson(services.follow_person),
        unfollow_person=ObservedUnfollowPerson(services.unfollow_person),
        list_timeline=ObservedListTimeline(services.list_timeline),
    )


class HttpTelemetry:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        name = {
            "/api/v1/people/search": "http.search",
            "/api/v1/guest-session": "http.bootstrap",
            "/api/v1/timeline": "http.timeline.list",
        }.get(scope["path"], "http.other")
        if scope["path"] == "/api/v1/following":
            name = {"GET": "http.following.list", "POST": "http.following.follow", "DELETE": "http.following.unfollow"}.get(scope["method"], "http.other")
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
        attributes = manager.__enter__()
        attributes["db.query.text"] = statement
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


def record_people_write(event: PeopleWriteEvent) -> None:
    with safe_span("people.persistence") as attributes:
        attributes.update(event_kind=event.kind, outstanding=event.outstanding, in_flight=event.in_flight, attempt=event.attempt, duration_ms=event.duration_ms)


class ObservedListTimeline:
    def __init__(self, inner: ListTimelinePort) -> None:
        self.inner = inner

    async def execute(self, request: TimelineRequest, context: GuestContext) -> TimelinePage:
        with safe_span('timeline.list') as attributes:
            try:
                return await self.inner.execute(request, context)
            except TimelineFailed as error:
                attributes['failure_category'] = error.category if error.category in TIMELINE_FAILURE_CATEGORIES else 'internal'
                raise
            except TimeoutError:
                attributes['failure_category'] = 'deadline'
                raise


class ObservedListFollowing:
    def __init__(self, inner: ListFollowingPort) -> None:
        self.inner = inner

    async def execute(self, context: GuestContext) -> FollowingSnapshot:
        with safe_span('following.list') as attributes:
            try:
                return await self.inner.execute(context)
            except (FollowingFailed, SearchFailed) as error:
                attributes['failure_category'] = error.category if error.category in _CATEGORIES else 'internal'
                raise
            except TimeoutError:
                attributes['failure_category'] = 'deadline'
                raise


class ObservedFollowPerson:
    def __init__(self, inner: FollowPersonPort) -> None:
        self.inner = inner

    async def execute(self, identity: PersonIdentity, context: GuestContext) -> FollowingSnapshot:
        with safe_span('following.follow') as attributes:
            try:
                return await self.inner.execute(identity, context)
            except (FollowingFailed, SearchFailed) as error:
                attributes['failure_category'] = error.category if error.category in _CATEGORIES else 'internal'
                raise
            except TimeoutError:
                attributes['failure_category'] = 'deadline'
                raise


class ObservedUnfollowPerson:
    def __init__(self, inner: UnfollowPersonPort) -> None:
        self.inner = inner

    async def execute(self, identity: PersonIdentity, context: GuestContext) -> None:
        with safe_span('following.unfollow') as attributes:
            try:
                await self.inner.execute(identity, context)
            except (FollowingFailed, SearchFailed) as error:
                attributes['failure_category'] = error.category if error.category in _CATEGORIES else 'internal'
                raise
            except TimeoutError:
                attributes['failure_category'] = 'deadline'
                raise


def record_hydration(event: HydrationEvent) -> None:
    with safe_span("filmography.queue") as attributes:
        attributes.update(
            event_kind=event.kind if event.kind in _HYDRATION_EVENT_KINDS else "internal",
            outstanding=event.outstanding,
            in_flight=event.in_flight,
            attempt=event.attempt,
            duration_ms=event.duration_ms,
        )


class ObservedFilmographyCatalog:
    def __init__(self, inner: FilmographyCatalog) -> None:
        self.inner = inner

    async def fetch(self, identity: PersonIdentity) -> PersonFilmography:
        with safe_span("filmography.provider") as attributes:
            try:
                return await self.inner.fetch(identity)
            except HydrationFailed as error:
                category = error.category
                attributes["failure_category"] = category if category in _HYDRATION_PROVIDER_CATEGORIES else "internal"
                raise


class ObservedHydrateFilmography(HydrateFilmography):
    @override
    async def execute(self, identity: PersonIdentity, context: GuestContext) -> None:
        with safe_span("filmography.hydrate") as attributes:
            try:
                await super().execute(identity, context)
            except SearchFailed as error:
                category = error.category if error.category in {"quota", "storage"} else "internal"
                attributes.update(failure_category=category, quota_outcome="rejected" if category == "quota" else "failed")
                raise
            except HydrationFailed as error:
                category = error.category
                attributes["failure_category"] = category if category == "storage" or category in _HYDRATION_PROVIDER_CATEGORIES else "internal"
                raise
