from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from lumiere.domain.access import UsagePolicy

Positive = Annotated[int, Field(gt=0)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, hide_input_in_errors=True, extra="ignore")
    database_url: SecretStr
    tmdb_access_token: SecretStr
    ip_hash_key: SecretStr
    tmdb_base_url: str = "https://api.themoviedb.org"
    trusted_proxy_cidrs: tuple[str, ...] = ()
    telemetry_enabled: bool = False
    search_cache_max_age_seconds: Positive = 300
    global_requests_per_minute: Positive
    session_requests_per_minute: Positive
    ip_requests_per_minute: Positive
    bootstrap_requests_per_ip_per_minute: Positive
    global_provider_daily: Positive
    session_provider_daily: Positive
    ip_provider_daily: Positive
    global_provider_total: Positive
    session_provider_total: Positive
    ip_provider_total: Positive

    @field_validator("database_url")
    @classmethod
    def validate_database(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("Postgres with psycopg is required")
        return value

    @field_validator("trusted_proxy_cidrs")
    @classmethod
    def validate_proxies(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        from ipaddress import ip_network

        for cidr in value:
            ip_network(cidr)
        return value

    @field_validator("ip_hash_key", "tmdb_access_token")
    @classmethod
    def validate_nonempty(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("a nonempty runtime value is required")
        return value

    def usage_policy(self) -> UsagePolicy:
        return UsagePolicy(**{name: getattr(self, name) for name in UsagePolicy.__dataclass_fields__})
