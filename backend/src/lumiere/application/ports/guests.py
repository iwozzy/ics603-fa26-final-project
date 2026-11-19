from datetime import datetime
from typing import Protocol
from uuid import UUID

from lumiere.domain.access import GuestBootstrap, GuestContext, StoredGuestIdentity


class GuestIdentityRepository(Protocol):
    async def find(self, token_digest: bytes) -> StoredGuestIdentity | None: ...
    async def create(self, profile_id: UUID, token_digest: bytes) -> None: ...


class GuestIdentities(Protocol):
    async def bootstrap(self, proof: str | None, ip_key: str, now: datetime) -> GuestBootstrap: ...
    async def resolve(self, proof: str | None, ip_key: str, now: datetime) -> GuestContext: ...
