from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime

from sqlalchemy import select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lumiere.adapters.outbound.persistence.models import (
    CounterRow,
    GuestProfileRow,
    GuestSessionRow,
    ReservationRow,
)
from lumiere.domain.access import (
    CounterKey,
    GuestContext,
    Reservation,
    ReservationRecord,
    StoredGuestSession,
)
from lumiere.domain.errors import SearchFailed


class PostgresUsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_counters(self, keys: tuple[CounterKey, ...]) -> dict[CounterKey, int]:
        ordered = sorted(set(keys))
        if not ordered:
            return {}
        await self.session.execute(insert(CounterRow).values([{**asdict(key), "count": 0} for key in ordered]).on_conflict_do_nothing())
        columns = (CounterRow.scope, CounterRow.subject, CounterRow.feature, CounterRow.window)
        rows = (await self.session.scalars(select(CounterRow).where(tuple_(*columns).in_([(key.scope, key.subject, key.feature, key.window) for key in ordered])).order_by(*columns).with_for_update())).all()
        return {CounterKey(row.scope, row.subject, row.feature, row.window): row.count for row in rows}

    async def add_counts(self, deltas: Mapping[CounterKey, int]) -> None:
        for key in sorted(deltas):
            await self.session.execute(update(CounterRow).where(CounterRow.scope == key.scope, CounterRow.subject == key.subject, CounterRow.feature == key.feature, CounterRow.window == key.window).values(count=CounterRow.count + deltas[key]))

    async def add_reservation(self, record: ReservationRecord) -> None:
        self.session.add(ReservationRow(id=record.id, provider_keys=[asdict(key) for key in record.provider_keys], state=record.state))
        await self.session.flush()

    async def get_reservation_for_update(self, reservation: Reservation) -> ReservationRecord:
        row = await self.session.scalar(select(ReservationRow).where(ReservationRow.id == reservation.id).with_for_update())
        if row is None:
            raise SearchFailed("reservation")
        return ReservationRecord(row.id, tuple(CounterKey(**key) for key in row.provider_keys), row.state)

    async def save_reservation(self, record: ReservationRecord) -> None:
        await self.session.execute(update(ReservationRow).where(ReservationRow.id == record.id).values(state=record.state))


class PostgresGuestSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find(self, token_digest: bytes, now: datetime) -> StoredGuestSession | None:
        row = await self.session.scalar(select(GuestSessionRow).where(GuestSessionRow.token_digest == token_digest, GuestSessionRow.expires_at > now))
        return StoredGuestSession(row.profile_id, row.id, row.expires_at) if row else None

    async def create(self, context: GuestContext, token_digest: bytes, expires_at: datetime) -> None:
        self.session.add(GuestProfileRow(id=context.profile_id))
        await self.session.flush()
        self.session.add(GuestSessionRow(id=context.session_id, profile_id=context.profile_id, token_digest=token_digest, expires_at=expires_at))
        await self.session.flush()
