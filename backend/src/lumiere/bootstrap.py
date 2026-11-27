import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
from sqlalchemy import text

from lumiere.adapters.inbound.http.deps import HttpServices
from lumiere.adapters.inbound.http.timeline_cursor import Base64TimelineCursorCodec
from lumiere.adapters.outbound.clients.tmdb_filmography.client import (
    TMDBFilmographyCatalog,
)
from lumiere.adapters.outbound.clients.tmdb_people.client import TMDBPeopleCatalog
from lumiere.adapters.outbound.persistence.filmography_unit_of_work import (
    PostgresFilmographyUnitOfWork,
)
from lumiere.adapters.outbound.persistence.following_unit_of_work import (
    PostgresFollowingUnitOfWork,
)
from lumiere.adapters.outbound.persistence.people_unit_of_work import (
    PostgresPeopleUnitOfWork,
)
from lumiere.adapters.outbound.persistence.pools import PoolRegistry
from lumiere.adapters.outbound.persistence.timeline_unit_of_work import (
    PostgresTimelineUnitOfWork,
)
from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork
from lumiere.application.filmography_hydrator import FilmographyHydrator
from lumiere.application.people_writer import PeopleWriter
from lumiere.application.provider_dispatch import ProviderDispatch
from lumiere.application.use_cases.following import (
    FollowPerson,
    ListFollowing,
    UnfollowPerson,
)
from lumiere.application.use_cases.guest_identity import GuestIdentityService
from lumiere.application.use_cases.list_timeline import ListTimeline
from lumiere.application.use_cases.search_people import SearchPeople
from lumiere.application.use_cases.usage_admission import UsageAdmissionService
from lumiere.config import Settings
from lumiere.observability import (
    ObservedFilmographyCatalog,
    ObservedHydrateFilmography,
    ObservedTransport,
    configure_observability,
    instrument_database,
    observe_services,
    record_catalog_counts,
    record_hydration,
    record_people_write,
)


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return asyncio.get_running_loop().time()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


@dataclass
class AppContainer:
    services: HttpServices
    client: httpx.AsyncClient
    pools: PoolRegistry
    admission: UsageAdmissionService
    people_writer: PeopleWriter
    filmography_hydrator: FilmographyHydrator
    _closing: asyncio.Task[None] | None = field(default=None, init=False, repr=False)

    async def startup(self) -> None:
        await self.admission.start(SystemClock().now())
        self.people_writer.start()
        self.filmography_hydrator.start()

    async def close(self) -> None:
        if self._closing is None:
            self._closing = asyncio.create_task(self._close_resources(), name="application-close")
        try:
            await asyncio.shield(self._closing)
        except asyncio.CancelledError:
            await asyncio.shield(self._closing)
            raise

    async def _close_resources(self) -> None:
        errors: list[BaseException] = []
        try:
            await self.filmography_hydrator.close()
        except BaseException as error:  # noqa: BLE001 — finish resource cleanup even on cancellation
            errors.append(error)
        results = await asyncio.gather(self.admission.close(), self.people_writer.close(), return_exceptions=True)
        errors.extend(result for result in results if isinstance(result, BaseException))
        try:
            await self.client.aclose()
        except BaseException as error:  # noqa: BLE001 — finish resource cleanup even on cancellation
            errors.append(error)
        try:
            await self.pools.close()
        except BaseException as error:  # noqa: BLE001 — finish resource cleanup
            errors.append(error)
        if errors:
            raise BaseExceptionGroup("application cleanup failed", errors)


def build_container(settings: Settings) -> AppContainer:
    configure_observability(settings.telemetry_enabled)
    pools = PoolRegistry()
    database_url = settings.database_url.get_secret_value()
    application = pools.register("application", database_url)
    people_pool = pools.register("people_writer", database_url)
    hydration_pool = pools.register("movie_hydration", database_url)
    instrument_database(application.engine.sync_engine)
    instrument_database(people_pool.engine.sync_engine)
    instrument_database(hydration_pool.engine.sync_engine)
    client = httpx.AsyncClient(base_url=settings.tmdb_base_url, headers={"Authorization": "Bearer " + settings.tmdb_access_token.get_secret_value()}, transport=ObservedTransport(httpx.AsyncHTTPTransport(http2=True, retries=0, limits=httpx.Limits(max_connections=20, max_keepalive_connections=10))), timeout=httpx.Timeout(5, connect=2), follow_redirects=False, trust_env=False)

    def uows() -> PostgresAccessUnitOfWork:
        return PostgresAccessUnitOfWork(application.sessions)

    async def ready() -> None:
        admission.check_ready()
        async with application.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    def following_uows() -> PostgresFollowingUnitOfWork:
        return PostgresFollowingUnitOfWork(application.sessions)

    def timeline_uows() -> PostgresTimelineUnitOfWork:
        return PostgresTimelineUnitOfWork(application.sessions)

    def filmography_uows() -> PostgresFilmographyUnitOfWork:
        return PostgresFilmographyUnitOfWork(hydration_pool.sessions)

    def people_uows() -> PostgresPeopleUnitOfWork:
        return PostgresPeopleUnitOfWork(people_pool.sessions)

    policy = settings.usage_policy()
    admission = UsageAdmissionService(uows, policy)
    people_writer = PeopleWriter(people_uows, report=record_people_write)
    clock = SystemClock()
    dispatch = ProviderDispatch(admission, clock)
    catalog = ObservedFilmographyCatalog(TMDBFilmographyCatalog(client, clock, on_throttle=dispatch.observe_throttle))
    hydrate = ObservedHydrateFilmography(filmography_uows, catalog, dispatch, clock)
    hydrator = FilmographyHydrator(hydrate, report=record_hydration)
    search = SearchPeople(TMDBPeopleCatalog(client, report=record_catalog_counts), admission, clock, people_writer)
    services = HttpServices(
        search,
        GuestIdentityService(uows, policy),
        settings.ip_hash_key.get_secret_value().encode(),
        settings.trusted_proxy_cidrs,
        ready,
        search_cache_max_age_seconds=settings.search_cache_max_age_seconds,
        list_following=ListFollowing(following_uows),
        follow_person=FollowPerson(following_uows, hydrator),
        unfollow_person=UnfollowPerson(following_uows),
        list_timeline=ListTimeline(timeline_uows, Base64TimelineCursorCodec()),
    )
    return AppContainer(observe_services(services), client, pools, admission, people_writer, hydrator)
