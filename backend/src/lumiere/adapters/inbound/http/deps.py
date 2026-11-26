from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from lumiere.application.ports.following import (
    FollowPersonPort,
    ListFollowingPort,
    UnfollowPersonPort,
)
from lumiere.application.ports.guests import GuestIdentities
from lumiere.application.ports.search import PeopleSearch
from lumiere.application.ports.timeline import ListTimelinePort


@dataclass(frozen=True)
class HttpServices:
    search_people: PeopleSearch
    guests: GuestIdentities
    ip_hash_key: bytes
    list_following: ListFollowingPort = field(kw_only=True)
    follow_person: FollowPersonPort = field(kw_only=True)
    unfollow_person: UnfollowPersonPort = field(kw_only=True)
    list_timeline: ListTimelinePort = field(kw_only=True)
    trusted_proxy_cidrs: tuple[str, ...] = ()
    ready: Callable[[], Awaitable[None]] | None = None
    search_cache_max_age_seconds: int = 300
