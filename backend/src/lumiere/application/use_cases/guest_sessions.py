import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import uuid4

from lumiere.application.ports.unit_of_work import UnitOfWorkFactory
from lumiere.application.use_cases.usage_admission import minute_window
from lumiere.domain.access import CounterKey, GuestContext, GuestSession, UsagePolicy
from lumiere.domain.errors import SearchFailed


def proof_digest(proof: str) -> bytes:
    return hashlib.sha256(proof.encode()).digest()


class GuestSessionsService:
    def __init__(self, uow_factory: UnitOfWorkFactory, policy: UsagePolicy) -> None:
        self.uow_factory = uow_factory
        self.policy = policy

    async def bootstrap(self, proof: str | None, ip_key: str, now: datetime) -> GuestSession:
        async with self.uow_factory() as uow:
            key = CounterKey("ip", ip_key, "guest_bootstrap", minute_window(now))
            counts = await uow.usage.lock_counters((key,))
            if counts[key] >= self.policy.bootstrap_requests_per_ip_per_minute:
                raise SearchFailed("bootstrap_quota")
            await uow.usage.add_counts({key: 1})
            stored = await uow.sessions.find(proof_digest(proof), now) if proof else None
            if stored is not None and proof is not None:
                result = GuestSession(GuestContext(stored.profile_id, stored.session_id, ip_key), proof, False)
            else:
                context = GuestContext(uuid4(), uuid4(), ip_key)
                new_proof = secrets.token_urlsafe(32)
                await uow.sessions.create(context, proof_digest(new_proof), now + timedelta(hours=24))
                result = GuestSession(context, new_proof, True)
            await uow.commit()
        return result

    async def resolve(self, proof: str | None, ip_key: str, now: datetime) -> GuestContext:
        if proof is None or len(proof) > 256:
            raise SearchFailed("session")
        async with self.uow_factory() as uow:
            stored = await uow.sessions.find(proof_digest(proof), now)
            if stored is None:
                raise SearchFailed("session")
            return GuestContext(stored.profile_id, stored.session_id, ip_key)
