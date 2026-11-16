from datetime import UTC, datetime, timedelta

import pytest

from lumiere.application.minute_limits import MinuteLimiter
from lumiere.domain.access import CounterKey
from lumiere.domain.errors import SearchFailed

NOW = datetime(2026, 11, 15, tzinfo=UTC)
FIRST = CounterKey("ip", "first", "guest_bootstrap", "2026-11-15T00:00")
SECOND = CounterKey("ip", "second", "guest_bootstrap", "2026-11-15T00:00")


def test_capacity_does_not_evict_active_limit_and_expired_entries_are_reclaimed() -> None:
    limiter = MinuteLimiter(max_entries=1)
    limiter.admit({FIRST: 1}, NOW)
    with pytest.raises(SearchFailed, match="bootstrap_quota"):
        limiter.admit({SECOND: 1}, NOW, "bootstrap_quota")
    with pytest.raises(SearchFailed, match="quota"):
        limiter.admit({FIRST: 1}, NOW)
    limiter.admit({SECOND: 1}, NOW + timedelta(minutes=1))


def test_rejection_does_not_increment_any_other_scope() -> None:
    limiter = MinuteLimiter()
    limiter.admit({FIRST: 1}, NOW)
    with pytest.raises(SearchFailed):
        limiter.admit({FIRST: 1, SECOND: 1}, NOW)
    limiter.admit({SECOND: 1}, NOW)
