from collections.abc import Mapping
from datetime import UTC, datetime

from lumiere.domain.access import CounterKey
from lumiere.domain.errors import SearchFailed


def minute_window(now: datetime) -> str:
    return now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M")


class MinuteLimiter:
    """Process-local fixed windows; never evict an active counter to admit work."""

    def __init__(self, *, max_entries: int = 10_000) -> None:
        if max_entries < 1:
            raise ValueError("minute capacity must be positive")
        self.max_entries = max_entries
        self.window = ""
        self.counts: dict[CounterKey, int] = {}

    def admit(self, limits: Mapping[CounterKey, int], now: datetime, category: str = "quota") -> None:
        window = minute_window(now)
        if window != self.window:
            self.counts.clear()
            self.window = window
        new_keys = sum(key not in self.counts for key in limits)
        if len(self.counts) + new_keys > self.max_entries or any(self.counts.get(key, 0) >= cap for key, cap in limits.items()):
            raise SearchFailed(category)
        for key in limits:
            self.counts[key] = self.counts.get(key, 0) + 1
