from collections import OrderedDict

from lumiere.domain.access import StoredGuestIdentity


class GuestIdentityCache:
    """Validated identities retained until LRU eviction or worker restart."""

    def __init__(self, max_entries: int = 10000) -> None:
        if max_entries <= 0:
            raise ValueError("guest cache capacity must be positive")
        self._max_entries = max_entries
        self._entries: OrderedDict[bytes, StoredGuestIdentity] = OrderedDict()

    def get(self, digest: bytes) -> StoredGuestIdentity | None:
        identity = self._entries.get(digest)
        if identity is None:
            return None
        self._entries.move_to_end(digest)
        return identity

    def put(self, digest: bytes, identity: StoredGuestIdentity) -> None:
        self._entries[digest] = identity
        self._entries.move_to_end(digest)
        if len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
