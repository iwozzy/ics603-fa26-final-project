import pytest
from pydantic import ValidationError

from lumiere.config import Settings


@pytest.fixture
def configured_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test@localhost/test")
    monkeypatch.setenv("TMDB_ACCESS_TOKEN", "synthetic-test-only")
    monkeypatch.setenv("IP_HASH_KEY", "synthetic-test-only")
    for name in (
        "GLOBAL_REQUESTS_PER_MINUTE", "SESSION_REQUESTS_PER_MINUTE", "IP_REQUESTS_PER_MINUTE",
        "BOOTSTRAP_REQUESTS_PER_IP_PER_MINUTE", "GLOBAL_PROVIDER_DAILY", "SESSION_PROVIDER_DAILY",
        "IP_PROVIDER_DAILY", "GLOBAL_PROVIDER_TOTAL", "SESSION_PROVIDER_TOTAL", "IP_PROVIDER_TOTAL",
    ):
        monkeypatch.setenv(name, "100")
    monkeypatch.delenv("SEARCH_CACHE_MAX_AGE_SECONDS", raising=False)


@pytest.mark.usefixtures("configured_environment")
def test_search_cache_lifetime_defaults_to_300_seconds() -> None:
    assert Settings().search_cache_max_age_seconds == 300


@pytest.mark.usefixtures("configured_environment")
@pytest.mark.parametrize("seconds", [10, 10001])
def test_search_cache_lifetime_from_environment(monkeypatch: pytest.MonkeyPatch, seconds: int) -> None:
    monkeypatch.setenv("SEARCH_CACHE_MAX_AGE_SECONDS", str(seconds))
    assert Settings().search_cache_max_age_seconds == seconds


@pytest.mark.usefixtures("configured_environment")
@pytest.mark.parametrize("value", ["0", "-1", "1.5", "invalid"])
def test_invalid_search_cache_lifetime_is_rejected(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("SEARCH_CACHE_MAX_AGE_SECONDS", value)
    with pytest.raises(ValidationError):
        Settings()
