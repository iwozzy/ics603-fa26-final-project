from datetime import datetime
from typing import Protocol

from lumiere.domain.access import GuestContext, GuestSession, StoredGuestSession


class GuestSessionRepository(Protocol):
    async def find(self, token_digest: bytes, now: datetime) -> StoredGuestSession | None: ...
    async def create(self, context: GuestContext, token_digest: bytes, expires_at: datetime) -> None: ...


class GuestSessions(Protocol):
    async def bootstrap(self, proof: str | None, ip_key: str, now: datetime) -> GuestSession: ...
    async def resolve(self, proof: str | None, ip_key: str, now: datetime) -> GuestContext: ...
