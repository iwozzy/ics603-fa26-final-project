import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, event

from lumiere.adapters.outbound.persistence.models import GuestCredentialRow
from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork
from lumiere.application.guest_cache import GuestIdentityCache
from lumiere.application.use_cases.guest_identity import GuestIdentityService
from lumiere.domain.access import UsagePolicy
from lumiere.domain.errors import SearchFailed

POLICY = UsagePolicy(100, 100, 100, 100, 2, 2, 2, 3, 3, 3)
NOW = datetime(2026, 11, 15, tzinfo=UTC)


async def test_credentials_persist_and_store_only_digests(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    service = GuestIdentityService(uows, POLICY)
    first = await service.bootstrap(None, "ip-a", NOW)
    reused = await service.bootstrap(first.proof, "ip-a", NOW)
    assert reused.proof == first.proof and not reused.is_new
    async with uows() as uow:
        assert await uow.guests.find(first.proof.encode()) is None
        stored = await uow.guests.find(hashlib.sha256(first.proof.encode()).digest())
        assert stored is not None
        assert stored.profile_id == first.context.profile_id
    assert (await service.resolve(first.proof, "ip-a", NOW + timedelta(days=2))).profile_id == first.context.profile_id


async def test_existing_session_uses_current_server_ip_key(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    service = GuestIdentityService(uows, POLICY)
    first = await service.bootstrap(None, "ip-a", NOW)
    resolved = await service.resolve(first.proof, "ip-b", NOW)
    reused = await service.bootstrap(first.proof, "ip-c", NOW)
    assert resolved.ip_key == "ip-b" and reused.context.ip_key == "ip-c"
    assert resolved.profile_id == first.context.profile_id == reused.context.profile_id


async def test_warm_resolve_emits_no_database_queries(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    service = GuestIdentityService(uows, POLICY)
    first = await service.bootstrap(None, "ip-a", NOW)
    calls: list[object] = []

    def count_call(*args: object) -> None:
        calls.append(None)

    async with uows() as probe:
        connection = await probe.session.connection()
        engine = connection.engine.sync_engine
        event.listen(engine, "before_cursor_execute", count_call)
        try:
            for ip in ("ip-b", "ip-c"):
                context = await service.resolve(first.proof, ip, NOW)
                assert context.profile_id == first.context.profile_id
                assert context.ip_key == ip
            assert calls == []
        finally:
            event.remove(engine, "before_cursor_execute", count_call)


async def test_deleted_credential_is_rechecked_after_eviction_or_worker_restart(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    service = GuestIdentityService(uows, POLICY, cache=GuestIdentityCache(max_entries=1))
    first = await service.bootstrap(None, "ip-a", NOW)
    async with uows() as uow:
        await uow.session.execute(delete(GuestCredentialRow).where(GuestCredentialRow.profile_id == first.context.profile_id))
        await uow.commit()
    later = NOW + timedelta(days=365)
    assert (await service.resolve(first.proof, "ip-b", later)).profile_id == first.context.profile_id
    with pytest.raises(SearchFailed, match="session"):
        await GuestIdentityService(uows, POLICY).resolve(first.proof, "ip-b", later)
    await service.bootstrap(None, "ip-a", later)
    with pytest.raises(SearchFailed, match="session"):
        await service.resolve(first.proof, "ip-b", later)
