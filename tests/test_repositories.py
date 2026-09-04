from datetime import date

from sqlalchemy import func, select

from ivf_scout.db.models import NewsItem
from ivf_scout.db.repositories import NewsRepository, SourceRepository
from ivf_scout.scanning.models import NewsCategory, RelevantNewsItem
from ivf_scout.seeds import INITIAL_SOURCES


def test_seed_sources_is_idempotent(session):
    repository = SourceRepository(session)
    for seed in INITIAL_SOURCES:
        repository.upsert_seed(seed)
    for seed in INITIAL_SOURCES:
        repository.upsert_seed(seed)

    assert len(repository.list_enabled()) == len(INITIAL_SOURCES)


def test_memphasys_uses_asx_announcements_page(session):
    repository = SourceRepository(session)
    for seed in INITIAL_SOURCES:
        repository.upsert_seed(seed)

    source = repository.get_enabled_by_slug("memphasys")

    assert source is not None
    assert source.domain == "memphasys.com"
    assert source.website_url == (
        "https://www.memphasys.com/investor-relations/asx-announcements/"
    )


def test_exact_url_is_saved_only_once(session):
    source = SourceRepository(session).upsert_seed(INITIAL_SOURCES[0])
    item = RelevantNewsItem(
        title="New IVF incubator",
        url="https://www.coopersurgical.com/news/new-incubator",
        published_at=date(2026, 9, 1),
        category=NewsCategory.NEW_PRODUCT,
        manufacturer_name="CooperSurgical",
        product_name="Example",
        summary="A concise factual summary.",
        why_relevant="It is relevant to IVF laboratories.",
        europe_relevance=None,
    )
    repository = NewsRepository(session)

    assert repository.save_new(source, [item]) == 1
    assert repository.save_new(source, [item]) == 0
    assert session.scalar(select(func.count()).select_from(NewsItem)) == 1
    assert repository.list_recent()[0].title == "New IVF incubator"
