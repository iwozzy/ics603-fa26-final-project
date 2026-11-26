import asyncio
from datetime import timedelta

from lumiere.application.ports.filmography import (
    FilmographyCatalog,
    FilmographyUnitOfWorkFactory,
)
from lumiere.application.ports.hydration_clock import HydrationClock
from lumiere.application.provider_dispatch import ProviderDispatch
from lumiere.domain.access import GuestContext
from lumiere.domain.errors import HydrationFailed
from lumiere.domain.filmography import PersonFilmography
from lumiere.domain.following import PersonIdentity

_FRESHNESS = timedelta(hours=24)


class HydrateFilmography:
    def __init__(
        self,
        factory: FilmographyUnitOfWorkFactory,
        catalog: FilmographyCatalog,
        dispatch: ProviderDispatch,
        clock: HydrationClock,
        *,
        max_attempts: int = 3,
        attempt_timeout: float = 5,
        retry_delay: float = 1,
    ) -> None:
        if max_attempts <= 0 or attempt_timeout <= 0 or retry_delay < 0:
            raise ValueError('hydration retry bounds must be positive')
        self.factory = factory
        self.catalog = catalog
        self.dispatch = dispatch
        self.clock = clock
        self._max_attempts = max_attempts
        self._attempt_timeout = attempt_timeout
        self._retry_delay = retry_delay

    async def execute(self, identity: PersonIdentity, context: GuestContext) -> None:
        for attempt in range(1, self._max_attempts + 1):
            if await self._is_fresh(identity):
                return
            try:
                payload = await self.dispatch.run(context, lambda: self._fetch(identity))
            except HydrationFailed as error:
                if not error.retryable or attempt == self._max_attempts:
                    raise
                await self.clock.sleep(self._retry_delay)
            else:
                await self._persist(payload)
                return

    async def _is_fresh(self, identity: PersonIdentity) -> bool:
        try:
            async with asyncio.timeout(self._attempt_timeout):
                async with self.factory() as uow:
                    last_hydrated = await uow.filmographies.last_hydrated(identity)
        except Exception:  # noqa: BLE001 — storage errors stay outside provider retry policy
            raise HydrationFailed('storage') from None
        return last_hydrated is not None and last_hydrated > self.clock.now() - _FRESHNESS

    async def _fetch(self, identity: PersonIdentity) -> PersonFilmography:
        try:
            # Dispatcher waits for rate, capacity, and cooldown before invoking this operation.
            async with asyncio.timeout(self._attempt_timeout):
                return await self.catalog.fetch(identity)
        except TimeoutError:
            raise HydrationFailed('provider_transport', retryable=True) from None

    async def _persist(self, payload: PersonFilmography) -> None:
        for attempt in range(1, self._max_attempts + 1):
            try:
                async with asyncio.timeout(self._attempt_timeout):
                    async with self.factory() as uow:
                        await uow.filmographies.upsert(payload)
                        await uow.commit()
            except Exception:  # noqa: BLE001 — bound retries without exposing storage errors
                if attempt == self._max_attempts:
                    raise HydrationFailed('storage') from None
                await self.clock.sleep(self._retry_delay)
            else:
                return
