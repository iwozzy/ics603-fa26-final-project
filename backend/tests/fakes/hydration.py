import asyncio
from datetime import UTC, datetime, timedelta

from lumiere.domain.access import GuestContext
from lumiere.domain.errors import SearchFailed


class ControlledHydrationClock:
    def __init__(self, now: datetime = datetime(2026, 11, 26, tzinfo=UTC)) -> None:
        self._now = now
        self._monotonic = 0.0
        self._sleepers: dict[asyncio.Future[None], float] = {}

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._monotonic

    async def sleep(self, seconds: float) -> None:
        sleeper: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._sleepers[sleeper] = self._monotonic + seconds
        try:
            await sleeper
        finally:
            del self._sleepers[sleeper]

    async def advance(self, seconds: float) -> None:
        self._monotonic += seconds
        self.jump_wall(timedelta(seconds=seconds))
        for sleeper, deadline in self._sleepers.items():
            if deadline <= self._monotonic and not sleeper.done():
                sleeper.set_result(None)
        await asyncio.sleep(0)

    def jump_wall(self, delta: timedelta) -> None:
        self._now += delta


class RecordingAdmission:
    def __init__(self) -> None:
        self.charged_contexts: list[GuestContext] = []
        self.reject = False

    async def admit_and_charge(self, context: GuestContext, now: datetime) -> None:
        if self.reject:
            raise SearchFailed("quota")
        self.charged_contexts.append(context)
