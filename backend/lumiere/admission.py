"""Single-event-loop local bounds. Public global/durable accounting is a release gate."""

from collections import deque
from time import monotonic


class LocalAdmission:
    def __init__(self, concurrency: int, per_minute: int, total: int):
        self.concurrency = concurrency
        self.per_minute = per_minute
        self.total = total
        self.in_flight = 0
        self.admitted = 0
        self._recent: deque[float] = deque()

    def acquire(self) -> bool:
        now = monotonic()
        while self._recent and self._recent[0] <= now - 60:
            self._recent.popleft()
        if (
            self.in_flight >= self.concurrency
            or self.admitted >= self.total
            or len(self._recent) >= self.per_minute
        ):
            return False
        self.in_flight += 1
        self.admitted += 1
        self._recent.append(now)
        return True

    def release(self) -> None:
        self.in_flight -= 1
