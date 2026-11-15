from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from lumiere.application.ports.search import PeopleSearch
from lumiere.application.ports.sessions import GuestSessions


@dataclass(frozen=True)
class HttpServices:
    search_people: PeopleSearch
    sessions: GuestSessions
    ip_hash_key: bytes
    trusted_proxy_cidrs: tuple[str, ...] = ()
    ready: Callable[[], Awaitable[None]] | None = None
    search_cache_max_age_seconds: int = 300
