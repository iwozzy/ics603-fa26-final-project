import asyncio
from collections import deque
from collections.abc import Awaitable, Callable

from lumiere.application.ports.hydration_clock import HydrationClock
from lumiere.application.ports.usage import UsageAdmission
from lumiere.domain.access import GuestContext
from lumiere.domain.errors import HydrationThrottled
from lumiere.domain.filmography import PersonFilmography

_START_WINDOW_SECONDS = 1.0
_MIN_COOLDOWN_SECONDS = 60.0


class ProviderDispatch:
    """Shared admission gate for hydration calls on a single event loop."""

    def __init__(
        self, admission: UsageAdmission, clock: HydrationClock, *, rate_limit: int = 10, max_in_flight: int = 10,
    ) -> None:
        if min(rate_limit, max_in_flight) <= 0:
            raise ValueError("provider dispatch limits must be positive")
        self._admission = admission
        self._clock = clock
        self._rate_limit = rate_limit
        self._max_in_flight = max_in_flight
        self._starts: deque[float] = deque()
        self._cooldown_until = float("-inf")
        self._shutdown_deadline: float | None = None
        self._in_flight = 0
        self._capacity_available = asyncio.Event()
        self._capacity_available.set()

    def stop_at(self, deadline: float) -> None:
        """Reject new starts at the event loop's monotonic drain deadline."""
        self._shutdown_deadline = deadline

    def observe_throttle(self, error: HydrationThrottled) -> None:
        """Apply a 429 immediately, retaining its receipt time across stream cleanup."""
        if error.received_at_monotonic is None:
            error.received_at_monotonic = self._clock.monotonic()
        delay = max(_MIN_COOLDOWN_SECONDS, error.retry_after_seconds or 0)
        self._cooldown_until = max(self._cooldown_until, error.received_at_monotonic + delay)

    async def run(
        self, context: GuestContext, operation: Callable[[], Awaitable[PersonFilmography]],
    ) -> PersonFilmography:
        await self._wait_for_availability()
        now = self._clock.now()
        # Existing usage admission never yields. Gates, charge, and provider entry
        # happen in one event-loop turn.
        if self._shutdown_deadline is not None and asyncio.get_running_loop().time() >= self._shutdown_deadline:
            # A ready waiter can resume before the shutdown task cancels it.
            raise asyncio.CancelledError
        await self._admission.admit_and_charge(context, now)
        self._starts.append(self._clock.monotonic())
        self._in_flight += 1
        if self._in_flight == self._max_in_flight:
            self._capacity_available.clear()
        try:
            return await operation()
        except HydrationThrottled as error:
            self.observe_throttle(error)
            raise
        finally:
            self._in_flight -= 1
            self._capacity_available.set()

    async def _wait_for_availability(self) -> None:
        while True:
            if self._in_flight == self._max_in_flight:
                await self._capacity_available.wait()
                continue

            now = self._clock.monotonic()
            while self._starts and self._starts[0] + _START_WINDOW_SECONDS <= now:
                self._starts.popleft()
            ready_at = self._cooldown_until
            if len(self._starts) == self._rate_limit:
                ready_at = max(ready_at, self._starts[0] + _START_WINDOW_SECONDS)
            if ready_at <= now:
                return
            await self._clock.sleep(ready_at - now)
