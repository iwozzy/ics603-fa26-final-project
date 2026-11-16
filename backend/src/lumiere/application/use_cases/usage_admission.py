from datetime import UTC, datetime

from lumiere.application.ports.unit_of_work import UnitOfWorkFactory
from lumiere.domain.access import (
    CounterKey,
    GuestContext,
    UsagePolicy,
)
from lumiere.domain.errors import SearchFailed


def minute_window(now: datetime) -> str:
    return now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M")


def admission_limits(context: GuestContext, now: datetime, policy: UsagePolicy) -> dict[CounterKey, int]:
    limits: dict[CounterKey, int] = {}
    # Preserve existing SESSION_* configuration names for the per-guest caps.
    for scope, subject, policy_scope in (("global", "all", "global"), ("guest", str(context.profile_id), "session"), ("ip", context.ip_key, "ip")):
        limits[CounterKey(scope, subject, "people_request", minute_window(now))] = getattr(policy, f"{policy_scope}_requests_per_minute")
        limits[CounterKey(scope, subject, "people_provider", now.astimezone(UTC).date().isoformat())] = getattr(policy, f"{policy_scope}_provider_daily")
        limits[CounterKey(scope, subject, "people_provider", "total")] = getattr(policy, f"{policy_scope}_provider_total")
    return limits


class UsageAdmissionService:
    def __init__(self, uow_factory: UnitOfWorkFactory, policy: UsagePolicy) -> None:
        self.uow_factory = uow_factory
        self.policy = policy

    async def admit_and_charge(self, context: GuestContext, now: datetime) -> None:
        limits = admission_limits(context, now, self.policy)
        async with self.uow_factory() as uow:
            if not await uow.usage.admit_and_charge(limits):
                raise SearchFailed("quota")
            await uow.commit()
