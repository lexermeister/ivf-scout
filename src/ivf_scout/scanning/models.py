from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class NewsCategory(StrEnum):
    NEW_PRODUCT = "NEW_PRODUCT"
    PRODUCT_UPDATE = "PRODUCT_UPDATE"
    REGULATORY = "REGULATORY"
    TECHNOLOGY = "TECHNOLOGY"
    RESEARCH = "RESEARCH"
    PARTNERSHIP = "PARTNERSHIP"
    INDUSTRY_NEWS = "INDUSTRY_NEWS"


class RelevantNewsItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    url: HttpUrl
    published_at: date | None
    category: NewsCategory
    manufacturer_name: str | None
    product_name: str | None
    summary: str = Field(min_length=1, max_length=2000)
    why_relevant: str = Field(min_length=1, max_length=2000)
    europe_relevance: str | None


class SourceScanResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RelevantNewsItem] = Field(max_length=10)


class ScannedSourceResult(BaseModel):
    result: SourceScanResult
    response_id: str | None = None
