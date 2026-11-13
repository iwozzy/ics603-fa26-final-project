import math
import os
from dataclasses import dataclass, fields
from typing import Any


@dataclass(frozen=True)
class Settings:
    tmdb_token: str = ""
    provider_timeout: float = 5.0
    operation_timeout: float = 6.0
    max_query_chars: int = 200
    max_target_bytes: int = 4096
    max_provider_bytes: int = 1_048_576
    incoming_concurrency: int = 8
    outgoing_concurrency: int = 4
    admissions_per_minute: int = 60
    admission_total: int = 1000

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name != "tmdb_token" and (value <= 0 or not math.isfinite(value)):
                raise ValueError(f"Invalid setting: {field.name}")
        if self.operation_timeout <= self.provider_timeout:
            raise ValueError("Operation timeout must exceed provider timeout")

    @classmethod
    def from_env(cls):
        defaults = cls()
        values: dict[str, Any] = {}
        for field in fields(defaults):
            if field.name == "tmdb_token":
                values[field.name] = os.getenv("TMDB_API_READ_ACCESS_TOKEN", "")
            else:
                default = getattr(defaults, field.name)
                values[field.name] = type(default)(
                    os.getenv(f"WAYFINDER_{field.name.upper()}", str(default))
                )
        return cls(**values)
