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


def test_discovery_allows_article_id_on_same_path_as_index():
    html = """
    <a href="news.php?page=2">2</a>
    <div>Jul 31 2026 <a href="news.php?id=106">TSRM 2026</a></div>
    """
    source = Source(
        name="LensHooke",
        slug="lenshooke",
        domain="lenshooke.com",
        website_url="https://lenshooke.com/",
        news_url="https://lenshooke.com/news.php",
        article_url_patterns=["news.php?id="],
        scan_query="new andrology product launch",
        source_type="MANUFACTURER",
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=html))
    discoverer = SourceDiscoverer(20, client=httpx.Client(transport=transport))

    entries = discoverer.discover(source, date(2026, 7, 20), date(2026, 8, 1))

    assert len(entries) == 1
    assert entries[0].url == "https://lenshooke.com/news.php?id=106"
    assert entries[0].published_at == date(2026, 7, 31)


def test_discovery_finds_date_before_blog_card_content():
    filler = "".join(f"<p>context {index}</p>" for index in range(10))
    html = f"""
    <section>
      <p>September 3, 2026</p>
      <h2>New product</h2>
      {filler}
      <a href="/geneabiomedx/new-product/">More information</a>
    </section>
    """
    source = Source(
        name="Genea Biomedx",
        slug="genea-biomedx",
        domain="geneabiomedx.com",
        website_url="https://www.geneabiomedx.com/",
        news_url="https://www.geneabiomedx.com/blog/",
        article_url_patterns=["/geneabiomedx/"],
        scan_query="new IVF products",
        source_type="MANUFACTURER",
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=html))
    discoverer = SourceDiscoverer(20, client=httpx.Client(transport=transport))

    entries = discoverer.discover(source, date(2026, 8, 25), date(2026, 9, 8))

    assert len(entries) == 1
    assert entries[0].published_at == date(2026, 9, 3)
    assert entries[0].title == "New product"


def test_discovery_uses_sparmed_card_date_and_heading_for_image_link():
    html = """
    <div class="post">
      <div class="post__img"><a href="/en/news/old-regulatory-update/"><img></a></div>
      <div class="post__content">
        <time>4 August 2022</time>
        <h2><a href="/en/news/old-regulatory-update/">Medical Devices - Latest updates</a></h2>
      </div>
    </div>
    """
    source = Source(
        name="Sparmed",
        slug="sparmed",
        domain="sparmed.dk",
        website_url="https://www.sparmed.dk/",
        news_url="https://www.sparmed.dk/en/news/",
        article_url_patterns=["/en/news/"],
        scan_query="new IVF products",
        source_type="MANUFACTURER",
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=html))
    discoverer = SourceDiscoverer(20, client=httpx.Client(transport=transport))

    entries = discoverer.discover(source, date(2026, 8, 25), date(2026, 9, 8))

    assert entries == []


def test_discovery_ignores_genea_taxonomy_link():
    html = """
    <div class="post-card">
      <div class="post-card__terms">
        <a class="label-button" href="/news/geneabiomedx/">Genea Biomedx</a>
      </div>
      <span>September 7, 2026</span>
      <h4>Article title</h4>
      <a href="/geneabiomedx/article-title/">More information</a>
    </div>
    """
    source = Source(
        name="Genea Biomedx",
        slug="genea-biomedx",
        domain="geneabiomedx.com",
        website_url="https://www.geneabiomedx.com/",
        news_url="https://www.geneabiomedx.com/blog/",
        article_url_patterns=["/geneabiomedx/"],
        scan_query="new IVF products",
        source_type="MANUFACTURER",
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=html))
    discoverer = SourceDiscoverer(20, client=httpx.Client(transport=transport))

    entries = discoverer.discover(source, date(2026, 8, 25), date(2026, 9, 8))

    assert [(entry.title, entry.url) for entry in entries] == [
        ("Article title", "https://www.geneabiomedx.com/geneabiomedx/article-title/")
    ]
