from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from lumiere.application.use_cases.guest_identity import GuestIdentityService
from lumiere.domain.access import UsagePolicy
from lumiere.domain.errors import SearchFailed
from tests.fakes.access import MemoryAccess

NOW = datetime(2026, 11, 15, 23, 59, tzinfo=UTC)
POLICY = UsagePolicy(100, 100, 100, 100, 2, 2, 2, 3, 3, 3)


async def test_identity_persists_and_uses_current_ip() -> None:
    store = MemoryAccess()
    service = GuestIdentityService(store, POLICY)
    first = await service.bootstrap(None, "ip-a", NOW)
    reused = await service.bootstrap(first.proof, "ip-b", NOW)
    assert first.is_new and not reused.is_new
    assert reused.context.profile_id == first.context.profile_id
    assert reused.context.ip_key == "ip-b"
    resolved = await service.resolve(first.proof, "ip-c", NOW)
    assert resolved.ip_key == "ip-c"
    assert first.proof.encode() not in store.tokens
    assert len(next(iter(store.tokens))) == 32
    assert (await service.resolve(first.proof, "ip-a", NOW + timedelta(days=2))).profile_id == first.context.profile_id
    assert not (await service.bootstrap(first.proof, "ip-a", NOW + timedelta(days=2))).is_new


async def test_bootstrap_limit_and_missing_session_fail_closed() -> None:
    store = MemoryAccess()
    service = GuestIdentityService(store, replace(POLICY, bootstrap_requests_per_ip_per_minute=1))
    await service.bootstrap(None, "ip", NOW)
    with pytest.raises(SearchFailed):
        await service.bootstrap(None, "ip", NOW)
    with pytest.raises(SearchFailed):
        await service.resolve(None, "ip", NOW)
    assert len(store.tokens) == 1
