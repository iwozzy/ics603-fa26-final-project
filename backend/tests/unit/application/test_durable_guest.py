from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from lumiere.application.use_cases.guest_identity import GuestIdentityService
from lumiere.application.use_cases.usage_admission import UsageAdmissionService
from lumiere.domain.access import CounterKey, UsagePolicy
from lumiere.domain.errors import SearchFailed
from tests.fakes.access import MemoryAccess

NOW = datetime(2026, 11, 15, tzinfo=UTC)
POLICY = UsagePolicy(100, 100, 100, 100, 100, 100, 100, 100, 100, 100)


@pytest.mark.parametrize("days", [2, 365])
async def test_returning_guest_keeps_profile_and_cookie(days: int) -> None:
    access = MemoryAccess()
    first = await GuestIdentityService(access, POLICY).bootstrap(None, "ip-a", NOW)
    # A new service represents a restart or another worker with an empty cache.
    service = GuestIdentityService(access, POLICY)
    later = NOW + timedelta(days=days)
    returning = await service.bootstrap(first.proof, "ip-b", later)
    assert not returning.is_new
    assert returning.proof == first.proof
    assert returning.context.profile_id == first.context.profile_id
    assert returning.context.ip_key == "ip-b"
    assert (await service.resolve(first.proof, "ip-c", later)).profile_id == first.context.profile_id


async def test_identity_resolution_does_not_require_bootstrap_after_48_hours() -> None:
    access = MemoryAccess()
    first = await GuestIdentityService(access, POLICY).bootstrap(None, "ip-a", NOW)
    returning = await GuestIdentityService(access, POLICY).resolve(first.proof, "ip-b", NOW + timedelta(days=2))
    assert returning.profile_id == first.context.profile_id
    assert returning.ip_key == "ip-b"


async def test_cookie_renewal_does_not_reset_guest_total_budget() -> None:
    access = MemoryAccess()
    policy = replace(POLICY, session_provider_total=1)
    guests = GuestIdentityService(access, policy)
    admission = UsageAdmissionService(access, policy)
    await admission.start(NOW)
    first = await guests.bootstrap(None, "ip-a", NOW)
    await admission.admit_and_charge(first.context, NOW)
    later = NOW + timedelta(days=2)
    returning = await guests.bootstrap(first.proof, "ip-b", later)
    with pytest.raises(SearchFailed, match="quota"):
        await admission.admit_and_charge(returning.context, later)
    await admission.close()
    assert access.counts[CounterKey("guest", str(first.context.profile_id), "people_provider", "total")] == 1
