import asyncio
from collections.abc import Mapping
from copy import deepcopy
from types import TracebackType
from typing import Self
from uuid import UUID

from lumiere.application.ports.guests import GuestIdentityRepository
from lumiere.application.ports.usage import UsageRepository
from lumiere.domain.access import (
    CounterKey,
    StoredGuestIdentity,
)


class MemoryAccess:
    def __init__(self) -> None:
        self.counts: dict[CounterKey, int] = {}
        self.tokens: dict[bytes, StoredGuestIdentity] = {}
        self.lock = asyncio.Lock()
        self.commits = 0
        self.rollbacks = 0
        self.active = False

    def __call__(self) -> "MemoryUow":
        return MemoryUow(self)


class MemoryUow:
    def __init__(self, store: MemoryAccess) -> None:
        self.store = store
        self.usage: UsageRepository = self
        self.guests: GuestIdentityRepository = self
        self.committed = False

    async def __aenter__(self) -> Self:
        await self.store.lock.acquire()
        self.store.active = True
        self.snapshot = deepcopy((self.store.counts, self.store.tokens))
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        if not self.committed:
            await self.rollback()
        self.store.active = False
        self.store.lock.release()

    async def commit(self) -> None:
        self.committed = True
        self.store.commits += 1

    async def rollback(self) -> None:
        self.store.counts, self.store.tokens = self.snapshot
        self.store.rollbacks += 1

    async def lock_counters(self, keys: tuple[CounterKey, ...]) -> dict[CounterKey, int]:
        return {key: self.store.counts.get(key, 0) for key in keys}

    async def add_counts(self, deltas: Mapping[CounterKey, int]) -> None:
        for key, delta in deltas.items():
            self.store.counts[key] = self.store.counts.get(key, 0) + delta

    async def admit_and_charge(self, limits: Mapping[CounterKey, int]) -> bool:
        if any(self.store.counts.get(key, 0) >= cap for key, cap in limits.items()):
            return False
        await self.add_counts(dict.fromkeys(limits, 1))
        return True

    async def find(self, token_digest: bytes) -> StoredGuestIdentity | None:
        return self.store.tokens.get(token_digest)

    async def create(self, profile_id: UUID, token_digest: bytes) -> None:
        self.store.tokens[token_digest] = StoredGuestIdentity(profile_id)
