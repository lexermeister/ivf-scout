from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ivf_scout.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Source(TimestampMixin, Base):
    __tablename__ = "sources"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    website_url: Mapped[str] = mapped_column(String(500), nullable=False)
    scan_query: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_scan_status: Mapped[str | None] = mapped_column(String(20))
    last_scan_error: Mapped[str | None] = mapped_column(Text)

    news_items: Mapped[list[NewsItem]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class NewsItem(TimestampMixin, Base):
    __tablename__ = "news_items"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False, unique=True)
    published_at: Mapped[date | None] = mapped_column(Date, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    manufacturer_name: Mapped[str | None] = mapped_column(String(255))
    product_name: Mapped[str | None] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    why_relevant: Mapped[str] = mapped_column(Text, nullable=False)
    europe_relevance: Mapped[str | None] = mapped_column(Text)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    source: Mapped[Source] = relationship(back_populates="news_items")
