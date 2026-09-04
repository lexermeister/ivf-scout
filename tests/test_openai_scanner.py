import json
from datetime import date
from types import SimpleNamespace

from ivf_scout.config import Settings
from ivf_scout.db.models import Source
from ivf_scout.scanning.openai_scanner import OpenAISourceScanner


class FakeResponses:
    def __init__(self, payload):
        self.payload = payload
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(id="resp_test", output_text=json.dumps(self.payload))


def test_scanner_restricts_search_and_filters_external_urls():
    responses = FakeResponses(
        {
            "items": [
                {
                    "title": "Relevant launch",
                    "url": "https://www.coopersurgical.com/press-release/example",
                    "published_at": "2026-09-01",
                    "category": "NEW_PRODUCT",
                    "manufacturer_name": "CooperSurgical",
                    "product_name": "Example",
                    "summary": "Summary",
                    "why_relevant": "Relevant",
                    "europe_relevance": None,
                },
                {
                    "title": "External copy",
                    "url": "https://example.com/copied-release",
                    "published_at": "2026-09-01",
                    "category": "NEW_PRODUCT",
                    "manufacturer_name": "CooperSurgical",
                    "product_name": "Example",
                    "summary": "Summary",
                    "why_relevant": "Relevant",
                    "europe_relevance": None,
                },
            ]
        }
    )
    client = SimpleNamespace(responses=responses)
    settings = Settings(openai_api_key="test", openai_model="test-model")
    source = Source(
        name="CooperSurgical",
        slug="cooper-surgical",
        domain="coopersurgical.com",
        website_url="https://www.coopersurgical.com",
        scan_query="IVF product launch",
        source_type="MANUFACTURER",
    )

    result = OpenAISourceScanner(settings, client=client).scan(
        source, date(2026, 8, 26), date(2026, 9, 2)
    )

    assert len(result.result.items) == 1
    assert result.response_id == "resp_test"
    assert responses.kwargs["tools"][0]["filters"] == {"allowed_domains": ["coopersurgical.com"]}
    assert responses.kwargs["text"]["format"]["strict"] is True
