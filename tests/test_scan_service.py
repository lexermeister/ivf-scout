from datetime import UTC, date, datetime

from ivf_scout.db.repositories import SourceRepository
from ivf_scout.scanning.models import ScannedSourceResult, SourceScanResult
from ivf_scout.scanning.service import ScanService
from ivf_scout.seeds import INITIAL_SOURCES


class FakeScanner:
    def __init__(self, failing_slug=None):
        self.failing_slug = failing_slug
        self.windows = []

    def scan(self, source, start_date: date, end_date: date):
        self.windows.append((source.slug, start_date, end_date))
        if source.slug == self.failing_slug:
            raise RuntimeError("temporary failure")
        return ScannedSourceResult(result=SourceScanResult(items=[]), response_id="resp_test")


def test_scan_continues_after_source_failure(session):
    repository = SourceRepository(session)
    for seed in INITIAL_SOURCES[:2]:
        repository.upsert_seed(seed)
    session.commit()

    summary = ScanService(
        session, FakeScanner(failing_slug="cooper-surgical"), lookback_days=7
    ).run()

    assert summary.succeeded == 1
    assert summary.failed == 1
    failed = repository.get_enabled_by_slug("cooper-surgical")
    assert failed.last_scan_status == "FAILED"
    assert failed.last_scan_error == "temporary failure"


def test_lookback_applies_to_previously_scanned_source(session):
    repository = SourceRepository(session)
    repository.upsert_seed(INITIAL_SOURCES[0])
    source = repository.get_enabled_by_slug(INITIAL_SOURCES[0]["slug"])
    source.last_scanned_at = datetime(2026, 9, 4, 11, 37, tzinfo=UTC)
    session.commit()

    now = datetime(2026, 9, 4, 12, tzinfo=UTC)
    scanner = FakeScanner()
    service = ScanService(
        session,
        scanner,
        lookback_days=14,
    )

    assert service._start_date(source, now) == date(2026, 8, 21)
