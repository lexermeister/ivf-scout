from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://ivf_scout:ivf_scout@localhost:5433/ivf_scout"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.5"
    scan_lookback_days: int = Field(default=7, ge=1, le=90)
    openai_max_tool_calls: int = Field(default=3, ge=1, le=10)
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
