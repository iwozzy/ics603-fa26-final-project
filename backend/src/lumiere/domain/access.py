from dataclasses import dataclass, fields
from uuid import UUID


@dataclass(frozen=True)
class GuestContext:
    profile_id: UUID
    ip_key: str


@dataclass(frozen=True)
class GuestBootstrap:
    context: GuestContext
    proof: str
    is_new: bool


@dataclass(frozen=True, order=True)
class CounterKey:
    scope: str
    subject: str
    feature: str
    window: str


@dataclass(frozen=True)
class StoredGuestIdentity:
    profile_id: UUID


@dataclass(frozen=True)
class UsagePolicy:
    global_requests_per_minute: int
    session_requests_per_minute: int
    ip_requests_per_minute: int
    bootstrap_requests_per_ip_per_minute: int
    global_provider_daily: int
    session_provider_daily: int
    ip_provider_daily: int
    global_provider_total: int
    session_provider_total: int
    ip_provider_total: int

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not int or value <= 0:
                raise ValueError("usage caps must be positive integers")
