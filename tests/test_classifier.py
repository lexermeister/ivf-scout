import json
from datetime import date
from types import SimpleNamespace

from ivf_scout.config import Settings
from ivf_scout.db.models import Source
from ivf_scout.scanning.classifier import OpenAIContentClassifier
from ivf_scout.scanning.models import ArticleDocument


class FakeResponses:
    def __init__(self, payload):
        self.payload = payload
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            id="resp_test",
            output_text=json.dumps(self.payload),
            usage=SimpleNamespace(input_tokens=400, output_tokens=100),
        )


def test_classifier_uses_supplied_content_without_web_search():
    responses = FakeResponses(
        {
            "items": [
                {
                    "entry_id": "entry-1",
                    "relevant": True,
                    "title": "Four IVF innovations",
                    "published_at": None,
                    "category": "NEW_PRODUCT",
                    "manufacturer_name": "Minitube Human ART",
                    "product_name": "MiniQube",
                    "summary": "Four technologies were introduced.",
                    "why_relevant": "The products target IVF and andrology laboratories.",
                    "europe_relevance": "Presented at ESHRE in London.",
                }
            ]
        }
    )
    source = Source(
        name="Minitube Human ART",
        slug="minitube-human-art",
        domain="minitube-humanart.com",
        website_url="https://www.minitube-humanart.com/",
        news_url="https://www.minitube-humanart.com/en/news/",
        article_url_patterns=["/en/news/"],
        scan_query="IVF product innovation",
        source_type="MANUFACTURER",
    )
    document = ArticleDocument(
        entry_id="entry-1",
        url="https://www.minitube-humanart.com/en/news/example/",
        title="Four IVF innovations",
        published_at=date(2026, 8, 30),
        content="Minitube introduced four products for IVF laboratories.",
        content_type="text/html",
        content_hash="hash",
    )
    client = SimpleNamespace(responses=responses)

    result = OpenAIContentClassifier(
        Settings(openai_api_key="test", openai_model="test-model"), client=client
    ).classify(source, [document])

    assert result.items[0].relevant is True
    assert result.input_tokens == 400
    assert result.output_tokens == 100
    assert "tools" not in responses.kwargs
    assert responses.kwargs["reasoning"] == {"effort": "low"}
    assert responses.kwargs["text"]["format"]["strict"] is True
