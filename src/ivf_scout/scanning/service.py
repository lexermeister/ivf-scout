from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

from sqlalchemy.orm import Session

from ivf_scout.db.models import Source, SourceEntry
from ivf_scout.db.repositories import (
    NewsRepository,
    ScanRunRepository,
    SourceEntryRepository,
    SourceRepository,
)
from ivf_scout.scanning.models import (
    ArticleDocument,
    ClassificationResult,
    DiscoveredEntry,
    RelevantNewsItem,
)


class Discoverer(Protocol):
    def discover(
        self, source: Source, start_date: date, end_date: date
    ) -> list[DiscoveredEntry]: ...


class Fetcher(Protocol):
    def fetch(self, entry: SourceEntry) -> ArticleDocument: ...


class Classifier(Protocol):
    def classify(
        self, source: Source, documents: list[ArticleDocument]
    ) -> ClassificationResult: ...


@dataclass
class SourceOutcome:
    source: str
    start_date: date | None = None
    end_date: date | None = None
    saved: int = 0
    discovered: int = 0
    new: int = 0
    classified: int = 0
    skipped: int = 0
    entry_failures: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0
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
        discoverer: Discoverer,
        fetcher: Fetcher,
        classifier: Classifier,
        lookback_days: int,
        batch_size: int,
        input_cost_per_million: float,
        output_cost_per_million: float,
    ) -> None:
        self.session = session
        self.discoverer = discoverer
        self.fetcher = fetcher
        self.classifier = classifier
        self.lookback_days = lookback_days
        self.batch_size = batch_size
        self.input_cost_per_million = input_cost_per_million
        self.output_cost_per_million = output_cost_per_million
        self.sources = SourceRepository(session)
        self.news = NewsRepository(session)
        self.entries = SourceEntryRepository(session)
        self.runs = ScanRunRepository(session)

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
                run = self.runs.start(source, now)
                discovered = self.discoverer.discover(source, start, now.date())
                new_entries = self.entries.record_discovered(source, discovered, now)
                documents: list[ArticleDocument] = []
                entry_failures = 0
                for entry in new_entries:
                    try:
                        document = self.fetcher.fetch(entry)
                        entry.content_type = document.content_type
                        entry.content_hash = document.content_hash
                        entry.published_at = document.published_at or entry.published_at
                        documents.append(document)
                    except Exception as exc:
                        entry_failures += 1
                        self.entries.mark_processed(entry, "FAILED", error=str(exc))

                saved = 0
                classified = 0
                input_tokens = 0
                output_tokens = 0
                entries_by_id = {str(entry.id): entry for entry in new_entries}
                documents_by_id = {document.entry_id: document for document in documents}
                for index in range(0, len(documents), self.batch_size):
                    batch = documents[index : index + self.batch_size]
                    result = self.classifier.classify(source, batch)
                    input_tokens += result.input_tokens
                    output_tokens += result.output_tokens
                    returned_ids: set[str] = set()
                    for classified_entry in result.items:
                        entry = entries_by_id.get(classified_entry.entry_id)
                        document = documents_by_id.get(classified_entry.entry_id)
                        if entry is None or document is None:
                            continue
                        returned_ids.add(classified_entry.entry_id)
                        classified += 1
                        if not classified_entry.relevant:
                            self.entries.mark_processed(entry, "IRRELEVANT")
                            continue
                        if not all(
                            [
                                classified_entry.title,
                                classified_entry.category,
                                classified_entry.product_name,
                                classified_entry.summary,
                                classified_entry.why_relevant,
                            ]
                        ):
                            entry_failures += 1
                            self.entries.mark_processed(
                                entry,
                                "FAILED",
                                error="New-product classification is incomplete",
                            )
                            continue
                        item = RelevantNewsItem(
                            title=classified_entry.title,
                            url=document.url,
                            published_at=(
                                classified_entry.published_at or document.published_at
                            ),
                            category=classified_entry.category,
                            manufacturer_name=classified_entry.manufacturer_name,
                            product_name=classified_entry.product_name,
                            summary=classified_entry.summary,
                            why_relevant=classified_entry.why_relevant,
                            europe_relevance=classified_entry.europe_relevance,
                        )
                        if self.news.save_classified(source, entry, item, result.response_id):
                            saved += 1
                        self.entries.mark_processed(entry, "RELEVANT")

                    for document in batch:
                        if document.entry_id not in returned_ids:
                            entry_failures += 1
                            self.entries.mark_processed(
                                entries_by_id[document.entry_id],
                                "FAILED",
                                error="Classifier omitted this entry",
                            )

                estimated_cost = (
                    input_tokens * self.input_cost_per_million
                    + output_tokens * self.output_cost_per_million
                ) / 1_000_000
                self.sources.mark_succeeded(source, now)
                self.runs.complete(
                    run,
                    datetime.now(UTC),
                    discovered_count=len(discovered),
                    new_count=len(new_entries),
                    classified_count=classified,
                    saved_count=saved,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost_usd=estimated_cost,
                )
                self.session.commit()
                summary.outcomes.append(
                    SourceOutcome(
                        source=source.name,
                        start_date=start,
                        end_date=now.date(),
                        saved=saved,
                        discovered=len(discovered),
                        new=len(new_entries),
                        classified=classified,
                        skipped=len(discovered) - len(new_entries),
                        entry_failures=entry_failures,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        estimated_cost_usd=estimated_cost,
                    )
                )
            except Exception as exc:
                self.session.rollback()
                self.sources.mark_failed(source, str(exc))
                failed_run = self.runs.start(source, now)
                self.runs.fail(failed_run, datetime.now(UTC), str(exc))
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
