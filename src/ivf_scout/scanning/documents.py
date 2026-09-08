from __future__ import annotations

from hashlib import sha256
from io import BytesIO

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader

from ivf_scout.db.models import SourceEntry
from ivf_scout.scanning.discovery import belongs_to_domain, extract_structured_date
from ivf_scout.scanning.models import ArticleDocument


class ArticleFetcher:
    def __init__(self, max_characters: int, client: httpx.Client | None = None) -> None:
        self.max_characters = max_characters
        self.client = client or httpx.Client(
            follow_redirects=True,
            timeout=25,
            headers={"User-Agent": "IVFScout/0.1 (+market-intelligence scanner)"},
        )

    def fetch(self, entry: SourceEntry) -> ArticleDocument:
        response = self.client.get(entry.url)
        response.raise_for_status()
        if not belongs_to_domain(str(response.url), entry.source.domain):
            raise ValueError(f"Article redirected outside {entry.source.domain}")
        if len(response.content) > 10_000_000:
            raise ValueError("Article exceeds the 10 MB download limit")

        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type == "application/pdf" or response.url.path.lower().endswith(".pdf"):
            title, published_at, text = self._parse_pdf(response.content, entry)
            content_type = "application/pdf"
        else:
            title, published_at, text = self._parse_html(response.text, entry)
            content_type = content_type or "text/html"

        text = " ".join(text.split())[: self.max_characters]
        if len(text) < 80:
            raise ValueError("Article contains too little readable text")

        return ArticleDocument(
            entry_id=str(entry.id),
            url=entry.url,
            title=title,
            published_at=published_at,
            content=text,
            content_type=content_type,
            content_hash=sha256(text.encode()).hexdigest(),
        )

    def _parse_html(self, html: str, entry: SourceEntry):
        soup = BeautifulSoup(html, "html.parser")
        published_at = entry.published_at or extract_structured_date(soup)
        title_element = soup.find("h1") or soup.find("title")
        title = title_element.get_text(" ", strip=True) if title_element else entry.title
        for element in soup.select("script, style, nav, footer, form, noscript"):
            element.decompose()
        body = soup.find("article") or soup.find("main") or soup.find("body") or soup
        return title, published_at, body.get_text(" ", strip=True)

    def _parse_pdf(self, content: bytes, entry: SourceEntry):
        reader = PdfReader(BytesIO(content))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:20])
        title = entry.title or (reader.metadata.title if reader.metadata else None)
        return title, entry.published_at, text
