from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Uuid, bindparam, func, select, tuple_, update
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

    async def load_counts(self, day: str) -> dict[CounterKey, int]:
        rows = (await self.session.scalars(select(CounterRow).where(CounterRow.feature == "people_provider", CounterRow.window.in_(("total", day))))).all()
        return self._counts(rows)

    async def flush_charges(self, writer_id: UUID, sequence: int, deltas: Mapping[CounterKey, int]) -> dict[CounterKey, int]:
        if sequence < 1 or not deltas or any(delta <= 0 or key.feature != "people_provider" for key, delta in deltas.items()):
            raise ValueError("invalid usage batch")
        if sequence > 2**63 - 1:
            raise ValueError("usage batch out of sequence")
        for key in deltas:
            if key.window != "total":
                date.fromisoformat(key.window)
        payload = [{**asdict(key), "count": deltas[key]} for key in sorted(deltas)]
        charges = func.lumiere_flush_charges(
            bindparam("writer_id", writer_id, type_=Uuid),
            bindparam("sequence", sequence, type_=BigInteger),
            bindparam("deltas", payload, type_=JSONB),
        ).table_valued(*CounterRow.__table__.columns)
        statement = select(CounterRow).from_statement(select(charges)).execution_options(populate_existing=True)
        rows = (await self.session.scalars(statement)).all()
        if not rows:
            raise ValueError("usage batch out of sequence")
        return self._counts(rows)

    @staticmethod
    def _counts(rows: Sequence[CounterRow]) -> dict[CounterKey, int]:
        return {CounterKey(row.scope, row.subject, row.feature, row.window): row.count for row in rows}

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
