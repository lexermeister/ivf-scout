from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import datetime
from ipaddress import ip_address
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ivf_scout.db.repositories import SourceRepository
from ivf_scout.db.session import create_database_engine, create_session_factory, session_scope
from ivf_scout.scanning.discovery import belongs_to_domain
from ivf_scout.seeds import ANY_NEW_IVF_PRODUCT

DOMAIN_PATTERN = re.compile(
    r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)"
)

session_factory = create_session_factory(create_database_engine())


def get_session() -> Iterator[Session]:
    with session_scope(session_factory) as session:
        yield session


class SourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    domain: str = Field(min_length=1, max_length=255)
    website_url: HttpUrl
    news_url: HttpUrl
    article_url_patterns: list[str] = Field(min_length=1, max_length=20)
    enabled: bool = True

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        normalized = value.lower().rstrip(".")
        if normalized == "localhost" or not DOMAIN_PATTERN.fullmatch(normalized):
            raise ValueError("domain must be a public hostname without a scheme or path")
        try:
            ip_address(normalized)
        except ValueError:
            return normalized
        raise ValueError("domain must be a public hostname, not an IP address")

    @field_validator("article_url_patterns")
    @classmethod
    def validate_patterns(cls, values: list[str]) -> list[str]:
        patterns = [value.strip() for value in values]
        if any(not value or len(value) > 500 for value in patterns):
            raise ValueError("article URL patterns must contain 1 to 500 characters")
        if len(set(patterns)) != len(patterns):
            raise ValueError("article URL patterns must be unique")
        return patterns

    @model_validator(mode="after")
    def validate_official_urls(self) -> SourceCreate:
        for field_name, url in (
            ("website_url", self.website_url),
            ("news_url", self.news_url),
        ):
            if not belongs_to_domain(str(url), self.domain):
                raise ValueError(f"{field_name} must belong to the configured domain")
        return self


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    domain: str
    website_url: str
    news_url: str
    article_url_patterns: list[str]
    scan_query: str
    source_type: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


app = FastAPI(title="IVF Scout API", version="0.1.0")


@app.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def create_source(payload: SourceCreate, session: Annotated[Session, Depends(get_session)]):
    repository = SourceRepository(session)
    if repository.get_by_slug(payload.slug) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Source slug already exists: {payload.slug}",
        )

    values = payload.model_dump(mode="json")
    values.update(
        scan_query=ANY_NEW_IVF_PRODUCT,
        source_type="MANUFACTURER",
    )
    try:
        return repository.create(values)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Source slug already exists: {payload.slug}",
        ) from exc
