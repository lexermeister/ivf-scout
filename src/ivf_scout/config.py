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
    openai_model: str = "gpt-5.6-luna"
    scan_lookback_days: int = Field(default=7, ge=1, le=90)
    discovery_max_candidates: int = Field(default=20, ge=1, le=100)
    classifier_batch_size: int = Field(default=5, ge=1, le=10)
    article_max_characters: int = Field(default=12_000, ge=1_000, le=50_000)
    openai_input_cost_per_million: float = Field(default=0.20, ge=0)
    openai_output_cost_per_million: float = Field(default=1.20, ge=0)
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
