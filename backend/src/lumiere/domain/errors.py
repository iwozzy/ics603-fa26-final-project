class SearchFailed(Exception):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)


class FollowingFailed(Exception):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)


class HydrationFailed(Exception):
    def __init__(self, category: str, *, retryable: bool = False) -> None:
        self.category = category
        self.retryable = retryable
        super().__init__(category)


class HydrationThrottled(HydrationFailed):
    def __init__(self, retry_after_seconds: float | None) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__("provider_throttled", retryable=True)
