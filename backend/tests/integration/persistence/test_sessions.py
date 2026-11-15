import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork
from lumiere.application.use_cases.guest_sessions import GuestSessionsService
from lumiere.domain.access import UsagePolicy
from lumiere.domain.errors import SearchFailed

POLICY = UsagePolicy(100, 100, 100, 100, 2, 2, 2, 3, 3, 3)
NOW = datetime(2026, 11, 15, tzinfo=UTC)


async def test_sessions_reuse_expire_and_store_only_digests(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    service = GuestSessionsService(uows, POLICY)
    first = await service.bootstrap(None, "ip-a", NOW)
    reused = await service.bootstrap(first.proof, "ip-a", NOW)
    assert reused.proof == first.proof and not reused.is_new
    async with uows() as uow:
        assert await uow.sessions.find(first.proof.encode(), NOW) is None
        stored = await uow.sessions.find(hashlib.sha256(first.proof.encode()).digest(), NOW)
        assert stored is not None
        assert stored.session_id == first.context.session_id
    with pytest.raises(SearchFailed):
        await service.resolve(first.proof, "ip-a", NOW + timedelta(days=1))


async def test_existing_session_uses_current_server_ip_key(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    service = GuestSessionsService(uows, POLICY)
    first = await service.bootstrap(None, "ip-a", NOW)
    resolved = await service.resolve(first.proof, "ip-b", NOW)
    reused = await service.bootstrap(first.proof, "ip-c", NOW)
    assert resolved.ip_key == "ip-b" and reused.context.ip_key == "ip-c"
    assert resolved.profile_id == first.context.profile_id == reused.context.profile_id
