from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from lumiere.application.ports.unit_of_work import UnitOfWorkFactory
from lumiere.domain.access import (
    AttemptOutcome,
    CounterKey,
    GuestContext,
    Reservation,
    ReservationRecord,
    UsagePolicy,
)
from lumiere.domain.errors import SearchFailed


def minute_window(now: datetime) -> str:
    return now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M")


def admission_limits(context: GuestContext, now: datetime, policy: UsagePolicy) -> dict[CounterKey, int]:
    limits: dict[CounterKey, int] = {}
    for scope, subject in (("global", "all"), ("session", str(context.session_id)), ("ip", context.ip_key)):
        limits[CounterKey(scope, subject, "people_request", minute_window(now))] = getattr(policy, f"{scope}_requests_per_minute")
        limits[CounterKey(scope, subject, "people_provider", now.astimezone(UTC).date().isoformat())] = getattr(policy, f"{scope}_provider_daily")
        limits[CounterKey(scope, subject, "people_provider", "total")] = getattr(policy, f"{scope}_provider_total")
    return limits


class UsageAdmissionService:
    def __init__(self, uow_factory: UnitOfWorkFactory, policy: UsagePolicy) -> None:
        self.uow_factory = uow_factory
        self.policy = policy

    async def admit(self, context: GuestContext, now: datetime) -> Reservation:
        limits = admission_limits(context, now, self.policy)
        async with self.uow_factory() as uow:
            counts = await uow.usage.lock_counters(tuple(sorted(limits)))
            if any(counts[key] >= cap for key, cap in limits.items()):
                raise SearchFailed("quota")
            await uow.usage.add_counts(dict.fromkeys(limits, 1))
            reservation = Reservation(uuid4())
            keys = tuple(sorted(key for key in limits if key.feature == "people_provider"))
            await uow.usage.add_reservation(ReservationRecord(reservation.id, keys, "reserved"))
            await uow.commit()
        return reservation

    async def mark_dispatched(self, reservation: Reservation) -> None:
        await self._transition(reservation, "dispatched", "reserved")

    async def finish(self, reservation: Reservation, outcome: AttemptOutcome) -> None:
        await self._transition(reservation, outcome.value, "dispatched")

    async def _transition(self, reservation: Reservation, state: str, expected: str) -> None:
        async with self.uow_factory() as uow:
            record = await uow.usage.get_reservation_for_update(reservation)
            if record.state == expected:
                await uow.usage.save_reservation(replace(record, state=state))
            await uow.commit()

    async def release_undispatched(self, reservation: Reservation) -> None:
        async with self.uow_factory() as uow:
            record = await uow.usage.get_reservation_for_update(reservation)
            if record.state == "reserved":
                await uow.usage.lock_counters(record.provider_keys)
                await uow.usage.add_counts(dict.fromkeys(record.provider_keys, -1))
                await uow.usage.save_reservation(replace(record, state="released"))
            await uow.commit()
