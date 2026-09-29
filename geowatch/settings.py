from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GeoWatchSettings(BaseSettings):
    """Validated runtime settings.

    Existing environment variable names remain authoritative; this model adds
    validation without changing the current operational contract.
    """

    model_config = SettingsConfigDict(
        env_prefix="GEOWATCH_",
        case_sensitive=False,
        extra="ignore",
    )

    db_url: str | None = Field(default=None, validation_alias="GEOWATCH_DB_URL")
    raw_bucket: str | None = Field(default=None, validation_alias="GEOWATCH_RAW_BUCKET")
    raw_prefix: str = Field(default="raw", validation_alias="GEOWATCH_RAW_PREFIX")
    raw_backend: str = Field(default="", validation_alias="GEOWATCH_RAW_BACKEND")
    api_token: str | None = Field(default=None, validation_alias="GEOWATCH_API_TOKEN")
    source_scheduler: bool = Field(default=False, validation_alias="GEOWATCH_SOURCE_SCHEDULER")
    source_scheduler_tick: int = Field(default=30, validation_alias="GEOWATCH_SOURCE_SCHEDULER_TICK")
    analysis_min_interval_seconds: int = Field(default=300, validation_alias="GEOWATCH_ANALYSIS_MIN_INTERVAL_SECONDS")
    strict_production: bool = Field(default=False, validation_alias="GEOWATCH_STRICT_PRODUCTION")
    external_scheduler: bool = Field(default=False, validation_alias="GEOWATCH_EXTERNAL_SCHEDULER")
    embedded_collector: bool = Field(default=False, validation_alias="GEOWATCH_EMBEDDED_COLLECTOR")
    phoenix_endpoint: str | None = Field(default=None, validation_alias="GEOWATCH_PHOENIX_ENDPOINT")
    service_name: str = Field(default="geopolitical-watch", validation_alias="GEOWATCH_SERVICE_NAME")
    environment: str = Field(default="development", validation_alias="GEOWATCH_ENVIRONMENT")

    @field_validator("source_scheduler_tick")
    @classmethod
    def _validate_tick(cls, value: int) -> int:
        if not 15 <= value <= 300:
            raise ValueError("source_scheduler_tick must be between 15 and 300 seconds")
        return value

    @field_validator("analysis_min_interval_seconds")
    @classmethod
    def _validate_analysis_interval(cls, value: int) -> int:
        if not 60 <= value <= 3600:
            raise ValueError("analysis_min_interval_seconds must be between 60 and 3600 seconds")
        return value

    @field_validator("raw_backend")
    @classmethod
    def _validate_raw_backend(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if normalized not in {"", "filesystem", "postgres", "postgresql", "gcs"}:
            raise ValueError("raw_backend must be filesystem, postgres/postgresql, gcs or empty")
        return normalized

    def validate_startup(self) -> dict[str, bool]:
        checks = {
            "database_configured": bool(self.db_url),
            "api_token_configured": bool(self.api_token and len(self.api_token) >= 32),
            "raw_persistent": bool(self.raw_bucket or self.raw_backend in {"postgres", "postgresql", "gcs"}),
            "scheduler_topology_valid": not (self.external_scheduler and self.source_scheduler),
        }
        if self.strict_production and not all(checks.values()):
            failed = sorted(name for name, ok in checks.items() if not ok)
            raise ValueError("strict production settings failed: " + ", ".join(failed))
        return checks


@lru_cache(maxsize=1)
def get_settings() -> GeoWatchSettings:
    return GeoWatchSettings()
