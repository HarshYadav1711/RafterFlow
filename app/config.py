"""Application settings loaded from environment / .env."""

from datetime import datetime
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Business logic must use reference_now, never wall clock."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    reference_now: datetime = Field(..., alias="REFERENCE_NOW")
    database_url: str = Field(..., alias="DATABASE_URL")
    admin_api_key: str = Field(..., alias="ADMIN_API_KEY")

    llm_provider: str = Field(default="", alias="LLM_PROVIDER")
    llm_base_url: str = Field(default="", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(default="", alias="LLM_MODEL")

    @field_validator("reference_now")
    @classmethod
    def must_be_timezone_aware(cls, value: datetime) -> datetime:
        # Fail loudly; never fall back to datetime.now().
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "REFERENCE_NOW must be a timezone-aware datetime "
                "(e.g. 2026-10-11T10:00:00+10:00)"
            )
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
