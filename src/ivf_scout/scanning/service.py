from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

from sqlalchemy.orm import Session

from ivf_scout.db.models import Source
from ivf_scout.db.repositories import NewsRepository, SourceRepository
from ivf_scout.scanning.models import ScannedSourceResult


class Scanner(Protocol):
    def scan(self, source: Source, start_date: date, end_date: date) -> ScannedSourceResult: ...


@dataclass
class SourceOutcome:
    source: str
    start_date: date | None = None
    end_date: date | None = None
    saved: int = 0
    status: str = "SUCCEEDED"
    error: str | None = None


@dataclass
class ScanSummary:
    outcomes: list[SourceOutcome] = field(default_factory=list)

    @property
    def saved(self) -> int:
        return sum(outcome.saved for outcome in self.outcomes)

    @property
    def succeeded(self) -> int:
        return sum(outcome.status == "SUCCEEDED" for outcome in self.outcomes)

    @property
    def failed(self) -> int:
        return sum(outcome.status == "FAILED" for outcome in self.outcomes)


class ScanService:
    def __init__(
        self,
        session: Session,
        scanner: Scanner,
        lookback_days: int,
    ) -> None:
        self.session = session
        self.scanner = scanner
        self.lookback_days = lookback_days
        self.sources = SourceRepository(session)
        self.news = NewsRepository(session)

    def run(self, source_slug: str | None = None) -> ScanSummary:
        if source_slug:
            source = self.sources.get_enabled_by_slug(source_slug)
            if source is None:
                raise ValueError(f"Enabled source not found: {source_slug}")
            sources = [source]
        else:
            sources = self.sources.list_enabled()

        summary = ScanSummary()
        for source in sources:
            now = datetime.now(UTC)
            start = self._start_date(source, now)
            try:
                scanned = self.scanner.scan(source, start, now.date())
                saved = self.news.save_new(source, scanned.result.items, scanned.response_id)
                self.sources.mark_succeeded(source, now)
                self.session.commit()
                summary.outcomes.append(
                    SourceOutcome(
                        source=source.name,
                        start_date=start,
                        end_date=now.date(),
                        saved=saved,
                    )
                )
            except Exception as exc:
                self.session.rollback()
                self.sources.mark_failed(source, str(exc))
                self.session.commit()
                summary.outcomes.append(
                    SourceOutcome(
                        source=source.name,
                        start_date=start,
                        end_date=now.date(),
                        status="FAILED",
                        error=str(exc),
                    )
                )
        return summary

    def _start_date(self, source: Source, now: datetime) -> date:
        return (now - timedelta(days=self.lookback_days)).date()
