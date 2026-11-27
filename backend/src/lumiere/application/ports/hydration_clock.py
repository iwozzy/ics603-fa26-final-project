from typing import Protocol

from lumiere.application.ports.clock import Clock


class HydrationClock(Clock, Protocol):
    def monotonic(self) -> float: ...
    async def sleep(self, seconds: float) -> None: ...
