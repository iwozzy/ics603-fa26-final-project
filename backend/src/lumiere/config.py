"""Configuration read exclusively from the process environment."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=None)

    cors_origins: list[str] = ["http://localhost:8081", "http://127.0.0.1:8081"]
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    telemetry_enabled: bool = False
