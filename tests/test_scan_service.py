from datetime import UTC, date, datetime

from ivf_scout.db.repositories import NewsRepository, SourceRepository
from ivf_scout.scanning.models import (
    ArticleDocument,
    ClassificationResult,
    ClassifiedEntry,
    DiscoveredEntry,
    NewsCategory,
)
from ivf_scout.scanning.service import ScanService
from ivf_scout.seeds import INITIAL_SOURCES


class FakeDiscoverer:
    def __init__(self, failing_slug=None):
        self.failing_slug = failing_slug

    def discover(self, source, start_date, end_date):
        if source.slug == self.failing_slug:
            raise RuntimeError("temporary failure")
        if source.slug != "minitube-human-art":
            return []
        return [
            DiscoveredEntry(
                url="https://www.minitube-humanart.com/en/news/four-innovations-6057/",
                title="Four innovations debut at ESHRE 2026",
            )
        ]


class FakeFetcher:
    def fetch(self, entry):
        return ArticleDocument(
            entry_id=str(entry.id),
            url=entry.url,
            title=entry.title,
            published_at=None,
            content="Four new IVF and andrology laboratory products were introduced at ESHRE.",
            content_type="text/html",
            content_hash="abc",
        )


class FakeClassifier:
    def __init__(self):
        self.calls = 0

    def classify(self, source, documents):
        self.calls += 1
        return ClassificationResult(
            items=[
                ClassifiedEntry(
                    entry_id=document.entry_id,
                    relevant=True,
                    title=document.title,
                    published_at=None,
                    category=NewsCategory.NEW_PRODUCT,
                    manufacturer_name="Minitube Human ART",
                    product_name="MiniQube",
                    summary="Four IVF and andrology products were introduced.",
                    why_relevant="They are new laboratory technologies.",
                    europe_relevance="Presented at ESHRE in London.",
                )
                for document in documents
            ],
            response_id="resp_test",
            input_tokens=400,
            output_tokens=100,
        )


def _service(session, discoverer, classifier):
    return ScanService(
        session,
        discoverer,
        FakeFetcher(),
        classifier,
        lookback_days=14,
        batch_size=5,
        input_cost_per_million=0.20,
        output_cost_per_million=1.20,
    )


def test_scan_continues_after_source_failure(session):
    repository = SourceRepository(session)
    for seed in INITIAL_SOURCES[:2]:
        repository.upsert_seed(seed)
    session.commit()

    summary = _service(
        session, FakeDiscoverer(failing_slug="cooper-surgical"), FakeClassifier()
    ).run()

    assert summary.succeeded == 1
    assert summary.failed == 1
    failed = repository.get_enabled_by_slug("cooper-surgical")
    assert failed.last_scan_status == "FAILED"
    assert failed.last_scan_error == "temporary failure"


def test_new_undated_article_is_classified_once_and_usage_is_counted(session):
    source_repository = SourceRepository(session)
    minitube_seed = next(seed for seed in INITIAL_SOURCES if seed["slug"] == "minitube-human-art")
    source_repository.upsert_seed(minitube_seed)
    session.commit()
    classifier = FakeClassifier()
    service = _service(session, FakeDiscoverer(), classifier)

    first = service.run(source_slug="minitube-human-art").outcomes[0]
    second = service.run(source_slug="minitube-human-art").outcomes[0]

    assert first.new == 1
    assert first.saved == 1
    assert first.input_tokens == 400
    assert first.output_tokens == 100
    assert first.estimated_cost_usd == 0.0002
    assert second.new == 0
    assert second.skipped == 1
    assert second.input_tokens == 0
    assert classifier.calls == 1
    assert len(NewsRepository(session).list_recent()) == 1


def test_lookback_applies_to_previously_scanned_source(session):
    repository = SourceRepository(session)
    repository.upsert_seed(INITIAL_SOURCES[0])
    source = repository.get_enabled_by_slug(INITIAL_SOURCES[0]["slug"])
    source.last_scanned_at = datetime(2026, 9, 4, 11, 37, tzinfo=UTC)
    session.commit()
    service = _service(session, FakeDiscoverer(), FakeClassifier())

    assert service._start_date(source, datetime(2026, 9, 4, 12, tzinfo=UTC)) == date(
        2026, 8, 21
    )
