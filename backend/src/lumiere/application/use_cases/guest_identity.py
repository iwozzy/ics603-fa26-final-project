import hashlib
import secrets
from datetime import datetime
from uuid import uuid4

from lumiere.application.guest_cache import GuestIdentityCache
from lumiere.application.ports.unit_of_work import UnitOfWorkFactory
from lumiere.application.use_cases.usage_admission import minute_window
from lumiere.domain.access import (
    CounterKey,
    GuestBootstrap,
    GuestContext,
    StoredGuestIdentity,
    UsagePolicy,
)
from lumiere.domain.errors import SearchFailed


def proof_digest(proof: str) -> bytes:
    return hashlib.sha256(proof.encode()).digest()


class GuestIdentityService:
    def __init__(self, uow_factory: UnitOfWorkFactory, policy: UsagePolicy, *, cache: GuestIdentityCache | None = None) -> None:
        self.uow_factory = uow_factory
        self.policy = policy
        self.cache = cache if cache is not None else GuestIdentityCache()

    async def bootstrap(self, proof: str | None, ip_key: str, now: datetime) -> GuestBootstrap:
        async with self.uow_factory() as uow:
            key = CounterKey("ip", ip_key, "guest_bootstrap", minute_window(now))
            counts = await uow.usage.lock_counters((key,))
            if counts[key] >= self.policy.bootstrap_requests_per_ip_per_minute:
                raise SearchFailed("bootstrap_quota")
            await uow.usage.add_counts({key: 1})
            stored = await uow.guests.find(proof_digest(proof)) if proof else None
            if stored is not None and proof is not None:
                result = GuestBootstrap(GuestContext(stored.profile_id, ip_key), proof, False)
            else:
                context = GuestContext(uuid4(), ip_key)
                new_proof = secrets.token_urlsafe(32)
                stored = StoredGuestIdentity(context.profile_id)
                await uow.guests.create(context.profile_id, proof_digest(new_proof))
                result = GuestBootstrap(context, new_proof, True)
            await uow.commit()
        self.cache.put(proof_digest(result.proof), stored)
        return result

    async def resolve(self, proof: str | None, ip_key: str, now: datetime) -> GuestContext:
        if proof is None or len(proof) > 256:
            raise SearchFailed("session")
        digest = proof_digest(proof)
        stored = self.cache.get(digest)
        if stored is None:
            async with self.uow_factory() as uow:
                stored = await uow.guests.find(digest)
                if stored is None:
                    raise SearchFailed("session")
            self.cache.put(digest, stored)
        return GuestContext(stored.profile_id, ip_key)
