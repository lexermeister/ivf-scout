from __future__ import annotations

import json
import re
from datetime import date
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup

from ivf_scout.db.models import Source
from ivf_scout.scanning.models import DiscoveredEntry

TRACKING_PARAMETERS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
DATE_PATTERNS = (
    (re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"), ("%Y-%m-%d",)),
    (
        re.compile(
            r"\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
            r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
            r"Dec(?:ember)?)\s+\d{1,2},\s+\d{4})\b",
            re.IGNORECASE,
        ),
        ("%B %d, %Y", "%b %d, %Y"),
    ),
    (
        re.compile(
            r"\b(\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
            r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
            r"Nov(?:ember)?|Dec(?:ember)?)\s+\d{4})\b",
            re.IGNORECASE,
        ),
        ("%d %B %Y", "%d %b %Y"),
    ),
)
PARTIAL_DATE_PATTERN = re.compile(
    r"\b(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)\b",
    re.IGNORECASE,
)


class SourceDiscoverer:
    def __init__(self, max_candidates: int, client: httpx.Client | None = None) -> None:
        self.max_candidates = max_candidates
        self.client = client or httpx.Client(
            follow_redirects=True,
            timeout=20,
            headers={"User-Agent": "IVFScout/0.1 (+market-intelligence scanner)"},
        )

    def discover(self, source: Source, start_date: date, end_date: date) -> list[DiscoveredEntry]:
        response = self.client.get(source.news_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        seen: set[str] = set()
        entries: list[DiscoveredEntry] = []
        news_url = canonicalize_url(source.news_url, source.news_url)
        news_path = urlsplit(news_url).path.rstrip("/") if news_url else ""

        for anchor in soup.select("a[href]"):
            url = canonicalize_url(anchor.get("href", ""), source.news_url)
            if not url or url == news_url or url in seen:
                continue
            if urlsplit(url).path.rstrip("/") == news_path:
                continue
            if not belongs_to_domain(url, source.domain):
                continue
            if not any(pattern.lower() in url.lower() for pattern in source.article_url_patterns):
                continue

            context_parts = [anchor.get_text(" ", strip=True)]
            parent_text = (anchor.parent or anchor).get_text(" ", strip=True)
            if len(parent_text) <= 1_000:
                context_parts.append(parent_text)
            previous_text = [
                str(value).strip()
                for value in anchor.find_all_previous(string=True, limit=5)
                if str(value).strip()
            ]
            context_parts.extend(previous_text)
            context = " ".join(context_parts)
            year_match = re.search(r"/(?:uploads/)?((?:19|20)\d{2})/", url)
            default_year = int(year_match.group(1)) if year_match else None
            published_at = extract_date(context, default_year=default_year)
            if published_at and not start_date <= published_at <= end_date:
                continue

            title = anchor.get_text(" ", strip=True) or None
            entries.append(DiscoveredEntry(url=url, title=title, published_at=published_at))
            seen.add(url)
            if len(entries) >= self.max_candidates:
                break

        return entries


def canonicalize_url(value: str, base_url: str) -> str | None:
    absolute = urljoin(base_url, value.strip())
    parts = urlsplit(absolute)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return None
    query = urlencode(
        [
            (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMETERS
        ]
    )
    netloc = parts.hostname.lower()
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", query, ""))


def belongs_to_domain(url: str, domain: str) -> bool:
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    expected = domain.lower().rstrip(".")
    return host == expected or host.endswith(f".{expected}")


def extract_date(text: str, default_year: int | None = None) -> date | None:
    from datetime import datetime

    for pattern, formats in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        for date_format in formats:
            try:
                return datetime.strptime(match.group(1), date_format).date()
            except ValueError:
                continue
    partial = PARTIAL_DATE_PATTERN.search(text)
    if partial and default_year:
        for date_format in ("%d %B %Y", "%d %b %Y"):
            try:
                return datetime.strptime(
                    f"{partial.group(1)} {partial.group(2)} {default_year}", date_format
                ).date()
            except ValueError:
                continue
    return None


def extract_structured_date(soup: BeautifulSoup) -> date | None:
    time_element = soup.find("time")
    if time_element:
        value = time_element.get("datetime") or time_element.get_text(" ", strip=True)
        parsed = extract_date(str(value))
        if parsed:
            return parsed

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        values = payload if isinstance(payload, list) else [payload]
        for value in values:
            if isinstance(value, dict):
                published = value.get("datePublished")
                parsed = extract_date(str(published)) if published else None
                if parsed:
                    return parsed
    return None
