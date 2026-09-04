from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ivf_scout.db.models import NewsItem, Source
from ivf_scout.scanning.models import RelevantNewsItem


class SourceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_enabled(self) -> list[Source]:
        statement = select(Source).where(Source.enabled.is_(True)).order_by(Source.name)
        return list(self.session.scalars(statement))

    def get_enabled_by_slug(self, slug: str) -> Source | None:
        statement = select(Source).where(Source.slug == slug, Source.enabled.is_(True))
        return self.session.scalar(statement)

    def upsert_seed(self, seed: dict[str, object]) -> Source:
        source = self.session.scalar(select(Source).where(Source.slug == seed["slug"]))
        if source is None:
            source = Source(**seed)
            self.session.add(source)
        else:
            for key, value in seed.items():
                setattr(source, key, value)
        self.session.flush()
        return source

    def mark_succeeded(self, source: Source, scanned_at: datetime) -> None:
        source.last_scanned_at = scanned_at
        source.last_scan_status = "SUCCEEDED"
        source.last_scan_error = None
        self.session.flush()

    def mark_failed(self, source: Source, error: str) -> None:
        source.last_scan_status = "FAILED"
        source.last_scan_error = error[:4000]
        self.session.flush()


class NewsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_new(
        self,
        source: Source,
        items: Iterable[RelevantNewsItem],
        response_id: str | None = None,
    ) -> int:
        saved = 0
        for item in items:
            url = str(item.url)
            if self.session.scalar(select(NewsItem.id).where(NewsItem.url == url)) is not None:
                continue
            self.session.add(
                NewsItem(
                    source_id=source.id,
                    title=item.title,
                    url=url,
                    published_at=item.published_at,
                    category=item.category.value,
                    manufacturer_name=item.manufacturer_name,
                    product_name=item.product_name,
                    summary=item.summary,
                    why_relevant=item.why_relevant,
                    europe_relevance=item.europe_relevance,
                    discovered_at=datetime.now(UTC),
                    extra_metadata={"openai_response_id": response_id} if response_id else {},
                )
            )
            saved += 1
        self.session.flush()
        return saved

    def list_recent(self, limit: int = 20) -> list[NewsItem]:
        statement = select(NewsItem).order_by(NewsItem.discovered_at.desc()).limit(limit)
        return list(self.session.scalars(statement))
