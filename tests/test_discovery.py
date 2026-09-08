from datetime import date

import httpx

from ivf_scout.db.models import Source
from ivf_scout.scanning.discovery import SourceDiscoverer, canonicalize_url


def _source() -> Source:
    return Source(
        name="Minitube Human ART",
        slug="minitube-human-art",
        domain="minitube-humanart.com",
        website_url="https://www.minitube-humanart.com/",
        news_url="https://www.minitube-humanart.com/en/news/",
        article_url_patterns=["/en/news/"],
        scan_query="IVF product innovation",
        source_type="MANUFACTURER",
    )


def test_discovery_keeps_new_undated_articles_and_ignores_navigation():
    html = """
    <main>
      <a href="/en/news/">News</a>
      <a href="/en/news/?page=2">2</a>
      <article><a href="/en/news/four-innovations-6057/?utm_source=test">
        Four innovations debut at ESHRE 2026
      </a></article>
      <a href="https://example.com/en/news/copied">External</a>
    </main>
    """
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=html))
    discoverer = SourceDiscoverer(20, client=httpx.Client(transport=transport))

    entries = discoverer.discover(_source(), date(2026, 8, 21), date(2026, 9, 4))

    assert len(entries) == 1
    assert entries[0].published_at is None
    assert entries[0].url == (
        "https://www.minitube-humanart.com/en/news/four-innovations-6057/"
    )


def test_canonicalize_url_removes_tracking_and_fragment():
    result = canonicalize_url(
        "/press-release/example/?utm_source=x&keep=yes#details",
        "https://www.coopersurgical.com/news/",
    )

    assert result == "https://www.coopersurgical.com/press-release/example/?keep=yes"


def test_discovery_uses_date_nearest_each_link():
    html = """
    <div class="all-announcements">
      <div>3 September 2026 - <a href="/wp-content/uploads/new.pdf">New</a></div>
      <div>20 August 2026 - <a href="/wp-content/uploads/old.pdf">Old</a></div>
    </div>
    """
    source = Source(
        name="Memphasys",
        slug="memphasys",
        domain="memphasys.com",
        website_url="https://www.memphasys.com/",
        news_url="https://www.memphasys.com/investor-relations/asx-announcements/",
        article_url_patterns=["/wp-content/uploads/"],
        scan_query="Felix IVF announcements",
        source_type="MANUFACTURER",
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=html))
    discoverer = SourceDiscoverer(20, client=httpx.Client(transport=transport))

    entries = discoverer.discover(source, date(2026, 8, 21), date(2026, 9, 4))

    assert [(entry.title, entry.published_at) for entry in entries] == [
        ("New", date(2026, 9, 3))
    ]


def test_discovery_infers_year_for_asx_dates_from_upload_url():
    html = """
    <div>9 February - <a href="/wp-content/uploads/2026/02/old.pdf">Old</a></div>
    """
    source = Source(
        name="Memphasys",
        slug="memphasys",
        domain="memphasys.com",
        website_url="https://www.memphasys.com/",
        news_url="https://www.memphasys.com/investor-relations/asx-announcements/",
        article_url_patterns=["/wp-content/uploads/"],
        scan_query="Felix IVF announcements",
        source_type="MANUFACTURER",
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=html))
    discoverer = SourceDiscoverer(20, client=httpx.Client(transport=transport))

    entries = discoverer.discover(source, date(2026, 8, 21), date(2026, 9, 4))

    assert entries == []
