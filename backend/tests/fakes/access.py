import asyncio
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime
from types import TracebackType
from typing import Self

from lumiere.application.ports.sessions import GuestSessionRepository
from lumiere.application.ports.usage import UsageRepository
from lumiere.domain.access import (
    CounterKey,
    GuestContext,
    Reservation,
    ReservationRecord,
    StoredGuestSession,
)


class MemoryAccess:
    def __init__(self) -> None:
        self.counts: dict[CounterKey, int] = {}
        self.records: dict[object, ReservationRecord] = {}
        self.tokens: dict[bytes, StoredGuestSession] = {}
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
        self.sessions: GuestSessionRepository = self
        self.committed = False

    async def __aenter__(self) -> Self:
        await self.store.lock.acquire()
        self.store.active = True
        self.snapshot = deepcopy((self.store.counts, self.store.records, self.store.tokens))
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
        self.store.counts, self.store.records, self.store.tokens = self.snapshot
        self.store.rollbacks += 1

    async def lock_counters(self, keys: tuple[CounterKey, ...]) -> dict[CounterKey, int]:
        return {key: self.store.counts.get(key, 0) for key in keys}

    async def add_counts(self, deltas: Mapping[CounterKey, int]) -> None:
        for key, delta in deltas.items():
            self.store.counts[key] = self.store.counts.get(key, 0) + delta

    async def add_reservation(self, record: ReservationRecord) -> None:
        self.store.records[record.id] = record

    async def get_reservation_for_update(self, reservation: Reservation) -> ReservationRecord:
        return self.store.records[reservation.id]

    async def save_reservation(self, record: ReservationRecord) -> None:
        self.store.records[record.id] = record

    async def find(self, token_digest: bytes, now: datetime) -> StoredGuestSession | None:
        session = self.store.tokens.get(token_digest)
        return session if session and session.expires_at > now else None

    async def create(self, context: GuestContext, token_digest: bytes, expires_at: datetime) -> None:
        self.store.tokens[token_digest] = StoredGuestSession(context.profile_id, context.session_id, expires_at)
