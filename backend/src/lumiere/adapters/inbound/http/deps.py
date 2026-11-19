from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from lumiere.application.ports.guests import GuestIdentities
from lumiere.application.ports.search import PeopleSearch


@dataclass(frozen=True)
class HttpServices:
    search_people: PeopleSearch
    guests: GuestIdentities
    ip_hash_key: bytes
    trusted_proxy_cidrs: tuple[str, ...] = ()
    ready: Callable[[], Awaitable[None]] | None = None
    search_cache_max_age_seconds: int = 300
