from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from lumiere.adapters.inbound.http.deps import HttpServices
from lumiere.adapters.outbound.clients.tmdb_people.client import TMDBPeopleCatalog
from lumiere.adapters.outbound.persistence.session import create_sessions
from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork
from lumiere.application.use_cases.guest_identity import GuestIdentityService
from lumiere.application.use_cases.search_people import SearchPeople
from lumiere.application.use_cases.usage_admission import UsageAdmissionService
from lumiere.config import Settings
from lumiere.observability import (
    ObservedTransport,
    configure_observability,
    instrument_database,
    observe_services,
    record_catalog_counts,
)


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass
class AppContainer:
    services: HttpServices
    client: httpx.AsyncClient
    engine: AsyncEngine
    admission: UsageAdmissionService

    async def startup(self) -> None:
        await self.admission.start(SystemClock().now())

    async def close(self) -> None:
        try:
            await self.admission.close()
        finally:
            try:
                await self.client.aclose()
            finally:
                await self.engine.dispose()


def build_container(settings: Settings) -> AppContainer:
    configure_observability(settings.telemetry_enabled)
    engine, sessions = create_sessions(settings.database_url.get_secret_value())
    instrument_database(engine.sync_engine)
    client = httpx.AsyncClient(base_url=settings.tmdb_base_url, headers={"Authorization": "Bearer " + settings.tmdb_access_token.get_secret_value()}, transport=ObservedTransport(httpx.AsyncHTTPTransport(http2=True, retries=0, limits=httpx.Limits(max_connections=20, max_keepalive_connections=10))), timeout=httpx.Timeout(5, connect=2), follow_redirects=False, trust_env=False)

    def uows() -> PostgresAccessUnitOfWork:
        return PostgresAccessUnitOfWork(sessions)

    async def ready() -> None:
        admission.check_ready()
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    policy = settings.usage_policy()
    admission = UsageAdmissionService(uows, policy)
    search = SearchPeople(TMDBPeopleCatalog(client, report=record_catalog_counts), admission, SystemClock())
    services = HttpServices(search, GuestIdentityService(uows, policy), settings.ip_hash_key.get_secret_value().encode(), settings.trusted_proxy_cidrs, ready, search_cache_max_age_seconds=settings.search_cache_max_age_seconds)
    return AppContainer(observe_services(services), client, engine, admission)
