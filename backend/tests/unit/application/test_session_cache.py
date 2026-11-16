from dataclasses import replace
from datetime import UTC, datetime, timedelta
from runpy import run_path
from types import TracebackType
from typing import cast, override
from uuid import uuid4

import pytest

import lumiere.application.guest_cache as cache_module
from lumiere.application.guest_cache import GuestIdentityCache
from lumiere.application.use_cases.guest_identity import (
    GuestIdentityService,
    proof_digest,
)
from lumiere.domain.access import StoredGuestIdentity, UsagePolicy
from lumiere.domain.errors import SearchFailed
from tests.fakes.access import MemoryAccess, MemoryUow

POLICY = UsagePolicy(100, 100, 100, 100, 100, 100, 100, 100, 100, 100)
NOW = datetime(2026, 11, 15, tzinfo=UTC)


class CountedAccess(MemoryAccess):
    def __init__(self) -> None:
        super().__init__()
        self.opens = 0
        self.error: Exception | None = None

    @override
    def __call__(self) -> MemoryUow:
        self.opens += 1
        if self.error is not None:
            raise self.error
        return super().__call__()


def test_cache_retention_is_independent_of_elapsed_monotonic_time(monkeypatch: pytest.MonkeyPatch) -> None:
    elapsed = 0.0
    # Isolate module loading so any restored default clock captures this timer.
    with monkeypatch.context() as patch:
        patch.setattr("time.monotonic", lambda: elapsed)
        assert cache_module.__file__ is not None
        cache_type = cast(type[GuestIdentityCache], run_path(cache_module.__file__)["GuestIdentityCache"])
    cache = cache_type()
    identity = StoredGuestIdentity(uuid4())
    cache.put(b"synthetic-digest", identity)
    elapsed = 10**12
    assert cache.get(b"synthetic-digest") == identity


async def test_bootstrap_warms_session_without_caching_request_ip() -> None:
    access = CountedAccess()
    service = GuestIdentityService(access, POLICY)
    first = await service.bootstrap(None, "ip-a", NOW)
    for ip in ("ip-b", "ip-c"):
        resolved = await service.resolve(first.proof, ip, NOW)
        assert resolved.profile_id == first.context.profile_id
        assert resolved.ip_key == ip
    assert access.opens == 1


async def test_cold_worker_falls_back_once_then_uses_validated_session() -> None:
    access = CountedAccess()
    first = await GuestIdentityService(access, POLICY).bootstrap(None, "ip-a", NOW)
    other_worker = GuestIdentityService(access, POLICY)
    assert (await other_worker.resolve(first.proof, "ip-b", NOW)).profile_id == first.context.profile_id
    assert access.opens == 2
    assert (await other_worker.resolve(first.proof, "ip-c", NOW)).ip_key == "ip-c"
    assert access.opens == 2


async def test_warm_session_resolves_during_storage_outage_but_miss_fails_closed() -> None:
    access = CountedAccess()
    service = GuestIdentityService(access, POLICY)
    first = await service.bootstrap(None, "ip-a", NOW)
    access.error = SearchFailed("storage")
    assert (await service.resolve(first.proof, "ip-b", NOW)).profile_id == first.context.profile_id
    with pytest.raises(SearchFailed, match="storage"):
        await service.resolve("synthetic-unknown-proof", "ip-b", NOW)


async def test_warm_session_does_not_bypass_bootstrap_quota() -> None:
    access = CountedAccess()
    service = GuestIdentityService(access, replace(POLICY, bootstrap_requests_per_ip_per_minute=1))
    first = await service.bootstrap(None, "ip-a", NOW)
    with pytest.raises(SearchFailed, match="bootstrap_quota"):
        await service.bootstrap(first.proof, "ip-a", NOW)


async def test_deleted_credential_stays_cached_until_eviction() -> None:
    access = CountedAccess()
    service = GuestIdentityService(access, POLICY, cache=GuestIdentityCache(max_entries=1))
    first = await service.bootstrap(None, "ip-a", NOW)
    access.tokens.clear()
    later = NOW + timedelta(days=365)
    resolved = await service.resolve(first.proof, "ip-b", later)
    assert resolved.profile_id == first.context.profile_id
    assert resolved.ip_key == "ip-b"
    assert access.opens == 1
    with pytest.raises(SearchFailed, match="session"):
        await GuestIdentityService(access, POLICY).resolve(first.proof, "ip-b", later)
    await service.bootstrap(None, "ip-a", later)
    with pytest.raises(SearchFailed, match="session"):
        await service.resolve(first.proof, "ip-b", later)
    assert access.opens == 4


async def test_lru_evicts_unaccessed_session_and_miss_rewarms() -> None:
    access = CountedAccess()
    cache = GuestIdentityCache(max_entries=2)
    service = GuestIdentityService(access, POLICY, cache=cache)
    first = await service.bootstrap(None, "ip-a", NOW)
    second = await service.bootstrap(None, "ip-a", NOW)
    await service.resolve(first.proof, "ip-a", NOW)
    await service.bootstrap(None, "ip-a", NOW)
    assert access.opens == 3
    await service.resolve(first.proof, "ip-a", NOW)
    assert access.opens == 3
    await service.resolve(second.proof, "ip-a", NOW)
    assert access.opens == 4
    await service.resolve(second.proof, "ip-b", NOW)
    assert access.opens == 4


@pytest.mark.parametrize("failure", ["commit", "ambiguous_commit", "exit"])
async def test_failed_bootstrap_never_publishes_session_to_cache(failure: str) -> None:
    access, cache = MemoryAccess(), GuestIdentityCache()
    digests: list[bytes] = []

    class BrokenUow(MemoryUow):
        @override
        async def commit(self) -> None:
            digests.extend(self.store.tokens)
            if failure == "commit":
                raise SearchFailed("storage")
            await super().commit()
            if failure == "ambiguous_commit":
                raise SearchFailed("storage")

        @override
        async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
            await super().__aexit__(exc_type, exc, tb)
            if failure == "exit":
                raise SearchFailed("storage")

    service = GuestIdentityService(lambda: BrokenUow(access), POLICY, cache=cache)
    with pytest.raises(SearchFailed, match="storage"):
        await service.bootstrap(None, "ip-a", NOW)
    assert len(digests) == 1
    assert cache.get(digests[0]) is None


async def test_failed_lookup_exit_does_not_warm_cache() -> None:
    access, cache = MemoryAccess(), GuestIdentityCache()
    first = await GuestIdentityService(access, POLICY).bootstrap(None, "ip-a", NOW)

    class BrokenUow(MemoryUow):
        @override
        async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
            await super().__aexit__(exc_type, exc, tb)
            raise SearchFailed("storage")

    service = GuestIdentityService(lambda: BrokenUow(access), POLICY, cache=cache)
    with pytest.raises(SearchFailed, match="storage"):
        await service.resolve(first.proof, "ip-b", NOW)
    assert cache.get(proof_digest(first.proof)) is None


async def test_only_digests_and_stored_identity_are_cached() -> None:
    access, cache = MemoryAccess(), GuestIdentityCache()
    first = await GuestIdentityService(access, POLICY, cache=cache).bootstrap(None, "ip-a", NOW)
    stored = cache.get(proof_digest(first.proof))
    assert stored is not None
    assert stored.profile_id == first.context.profile_id
    assert cache.get(first.proof.encode()) is None


async def test_missing_and_oversized_proofs_never_open_storage() -> None:
    access = CountedAccess()
    service = GuestIdentityService(access, POLICY)
    for proof in (None, "x" * 257):
        with pytest.raises(SearchFailed, match="session"):
            await service.resolve(proof, "ip-a", NOW)
    assert access.opens == 0


async def test_unknown_proofs_are_not_cached() -> None:
    access = CountedAccess()
    service = GuestIdentityService(access, POLICY)
    for _ in range(2):
        with pytest.raises(SearchFailed, match="session"):
            await service.resolve("synthetic-unknown-proof", "ip-a", NOW)
    assert access.opens == 2


@pytest.mark.parametrize("capacity", [0, -1])
def test_invalid_cache_capacity_is_rejected(capacity: int) -> None:
    with pytest.raises(ValueError):
        GuestIdentityCache(max_entries=capacity)
