import pytest
from pydantic import ValidationError

from lumiere.config import Settings


@pytest.fixture
def configured_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
        monkeypatch.delenv("LUMIERE_" + name.upper(), raising=False)
    monkeypatch.setenv("LUMIERE_DATABASE_URL", "postgresql+psycopg://test@localhost/test")
    monkeypatch.setenv("LUMIERE_TMDB_ACCESS_TOKEN", "synthetic-test-only")
    monkeypatch.setenv("LUMIERE_IP_HASH_KEY", "synthetic-test-only")
    for name in (
        "LUMIERE_GLOBAL_REQUESTS_PER_MINUTE", "LUMIERE_SESSION_REQUESTS_PER_MINUTE", "LUMIERE_IP_REQUESTS_PER_MINUTE",
        "LUMIERE_BOOTSTRAP_REQUESTS_PER_IP_PER_MINUTE", "LUMIERE_GLOBAL_PROVIDER_DAILY", "LUMIERE_SESSION_PROVIDER_DAILY",
        "LUMIERE_IP_PROVIDER_DAILY", "LUMIERE_GLOBAL_PROVIDER_TOTAL", "LUMIERE_SESSION_PROVIDER_TOTAL", "LUMIERE_IP_PROVIDER_TOTAL",
    ):
        monkeypatch.setenv(name, "100")
    monkeypatch.delenv("LUMIERE_SEARCH_CACHE_MAX_AGE_SECONDS", raising=False)


@pytest.mark.usefixtures("configured_environment")
def test_search_cache_lifetime_defaults_to_300_seconds() -> None:
    assert Settings().search_cache_max_age_seconds == 300


@pytest.mark.usefixtures("configured_environment")
@pytest.mark.parametrize("seconds", [10, 10001])
def test_search_cache_lifetime_from_environment(monkeypatch: pytest.MonkeyPatch, seconds: int) -> None:
    monkeypatch.setenv("LUMIERE_SEARCH_CACHE_MAX_AGE_SECONDS", str(seconds))
    assert Settings().search_cache_max_age_seconds == seconds


@pytest.mark.usefixtures("configured_environment")
@pytest.mark.parametrize("value", ["0", "-1", "1.5", "invalid"])
def test_invalid_search_cache_lifetime_is_rejected(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("LUMIERE_SEARCH_CACHE_MAX_AGE_SECONDS", value)
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.usefixtures("configured_environment")
def test_unprefixed_cache_lifetime_does_not_override_app_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEARCH_CACHE_MAX_AGE_SECONDS", "42")
    assert Settings().search_cache_max_age_seconds == 300


@pytest.mark.usefixtures("configured_environment")
def test_unprefixed_cap_cannot_satisfy_required_app_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LUMIERE_GLOBAL_PROVIDER_TOTAL")
    monkeypatch.setenv("GLOBAL_PROVIDER_TOTAL", "100")
    with pytest.raises(ValidationError) as error:
        Settings()
    assert [(item["loc"], item["type"]) for item in error.value.errors()] == [(("global_provider_total",), "missing")]


@pytest.mark.usefixtures("configured_environment")
def test_prefixed_optional_runtime_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMIERE_TMDB_BASE_URL", "http://provider.test")
    monkeypatch.setenv("LUMIERE_TRUSTED_PROXY_CIDRS", '["127.0.0.0/8"]')
    monkeypatch.setenv("LUMIERE_TELEMETRY_ENABLED", "true")
    settings = Settings()
    assert settings.tmdb_base_url == "http://provider.test"
    assert settings.trusted_proxy_cidrs == ("127.0.0.0/8",)
    assert settings.telemetry_enabled is True
