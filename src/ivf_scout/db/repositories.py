from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ivf_scout.db.models import NewsItem, ScanRun, Source, SourceEntry
from ivf_scout.scanning.models import DiscoveredEntry, RelevantNewsItem


class SourceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_enabled(self) -> list[Source]:
        statement = select(Source).where(Source.enabled.is_(True)).order_by(Source.name)
        return list(self.session.scalars(statement))

    def get_enabled_by_slug(self, slug: str) -> Source | None:
        statement = select(Source).where(Source.slug == slug, Source.enabled.is_(True))
        return self.session.scalar(statement)

    def get_by_slug(self, slug: str) -> Source | None:
        return self.session.scalar(select(Source).where(Source.slug == slug))

    def create(self, values: dict[str, object]) -> Source:
        source = Source(**values)
        self.session.add(source)
        self.session.flush()
        return source

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

    def save_classified(
        self,
        source: Source,
        entry: SourceEntry,
        item: RelevantNewsItem,
        response_id: str | None = None,
    ) -> bool:
        existing_id = self.session.scalar(
            select(NewsItem.id).where(NewsItem.url == str(item.url))
        )
        if existing_id is not None:
            return False
        self.session.add(
            NewsItem(
                source_id=source.id,
                source_entry_id=entry.id,
                title=item.title,
                url=str(item.url),
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
        self.session.flush()
        return True

    def list_recent(self, limit: int = 20) -> list[NewsItem]:
        statement = select(NewsItem).order_by(NewsItem.discovered_at.desc()).limit(limit)
        return list(self.session.scalars(statement))


class SourceEntryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record_discovered(
        self,
        source: Source,
        candidates: Iterable[DiscoveredEntry],
        seen_at: datetime,
    ) -> list[SourceEntry]:
        new_entries: list[SourceEntry] = []
        for candidate in candidates:
            entry = self.session.scalar(
                select(SourceEntry).where(SourceEntry.url == candidate.url)
            )
            if entry is not None:
                entry.last_seen_at = seen_at
                if entry.published_at is None and candidate.published_at is not None:
                    entry.published_at = candidate.published_at
                continue
            entry = SourceEntry(
                source_id=source.id,
                url=candidate.url,
                title=candidate.title,
                published_at=candidate.published_at,
                first_seen_at=seen_at,
                last_seen_at=seen_at,
                status="PENDING",
            )
            self.session.add(entry)
            new_entries.append(entry)
        self.session.flush()
        return new_entries

    def mark_processed(
        self,
        entry: SourceEntry,
        status: str,
        *,
        content_type: str | None = None,
        content_hash: str | None = None,
        published_at=None,
        error: str | None = None,
    ) -> None:
        entry.status = status
        entry.content_type = content_type or entry.content_type
        entry.content_hash = content_hash or entry.content_hash
        entry.published_at = published_at or entry.published_at
        entry.classification_error = error[:4000] if error else None
        self.session.flush()


class ScanRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def start(self, source: Source, started_at: datetime) -> ScanRun:
        run = ScanRun(source_id=source.id, started_at=started_at, status="RUNNING")
        self.session.add(run)
        self.session.flush()
        return run

    def complete(self, run: ScanRun, completed_at: datetime, **values) -> None:
        run.completed_at = completed_at
        run.status = "SUCCEEDED"
        for key, value in values.items():
            setattr(run, key, value)
        self.session.flush()

    def fail(self, run: ScanRun, completed_at: datetime, error: str) -> None:
        run.completed_at = completed_at
        run.status = "FAILED"
        run.error = error[:4000]
        self.session.flush()
