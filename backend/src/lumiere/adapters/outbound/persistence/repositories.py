from collections.abc import Mapping
from dataclasses import asdict
from uuid import UUID, uuid4

from sqlalchemy import bindparam, func, select, tuple_, update
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession

from lumiere.adapters.outbound.persistence.models import (
    CounterRow,
    GuestCredentialRow,
    GuestProfileRow,
)
from lumiere.domain.access import (
    CounterKey,
    StoredGuestIdentity,
)


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

    async def admit_and_charge(self, limits: Mapping[CounterKey, int]) -> bool:
        payload = [{**asdict(key), "cap": limits[key]} for key in sorted(limits)]
        statement = select(func.lumiere_admit_and_charge(bindparam("limits", payload, type_=JSONB)))
        return await self.session.scalar(statement) is True

class PostgresGuestIdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find(self, token_digest: bytes) -> StoredGuestIdentity | None:
        row = await self.session.scalar(select(GuestCredentialRow).where(GuestCredentialRow.token_digest == token_digest))
        return StoredGuestIdentity(row.profile_id) if row else None

    async def create(self, profile_id: UUID, token_digest: bytes) -> None:
        self.session.add(GuestProfileRow(id=profile_id))
        await self.session.flush()
        self.session.add(GuestCredentialRow(id=uuid4(), profile_id=profile_id, token_digest=token_digest))
        await self.session.flush()
