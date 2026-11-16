from collections.abc import Mapping
from datetime import datetime
from typing import Protocol

from lumiere.domain.access import CounterKey, GuestContext


class UsageAdmission(Protocol):
    async def admit_and_charge(self, context: GuestContext, now: datetime) -> None: ...


class UsageRepository(Protocol):
    async def lock_counters(self, keys: tuple[CounterKey, ...]) -> dict[CounterKey, int]: ...
    async def add_counts(self, deltas: Mapping[CounterKey, int]) -> None: ...
    async def admit_and_charge(self, limits: Mapping[CounterKey, int]) -> bool: ...
