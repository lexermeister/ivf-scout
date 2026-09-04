from __future__ import annotations

import json
from datetime import date
from typing import Any
from urllib.parse import urlparse

from openai import OpenAI

from ivf_scout.config import Settings
from ivf_scout.db.models import Source
from ivf_scout.scanning.models import ScannedSourceResult, SourceScanResult
from ivf_scout.scanning.prompt import SCANNER_INSTRUCTIONS, build_scan_prompt

SOURCE_SCAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "items": {
            "type": "array",
            "maxItems": 10,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "published_at": {"type": ["string", "null"], "format": "date"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "NEW_PRODUCT",
                            "PRODUCT_UPDATE",
                            "REGULATORY",
                            "TECHNOLOGY",
                            "RESEARCH",
                            "PARTNERSHIP",
                            "INDUSTRY_NEWS",
                        ],
                    },
                    "manufacturer_name": {"type": ["string", "null"]},
                    "product_name": {"type": ["string", "null"]},
                    "summary": {"type": "string"},
                    "why_relevant": {"type": "string"},
                    "europe_relevance": {"type": ["string", "null"]},
                },
                "required": [
                    "title",
                    "url",
                    "published_at",
                    "category",
                    "manufacturer_name",
                    "product_name",
                    "summary",
                    "why_relevant",
                    "europe_relevance",
                ],
            },
        }
    },
    "required": ["items"],
}


class OpenAISourceScanner:
    def __init__(self, settings: Settings, client: OpenAI | None = None) -> None:
        if not settings.openai_api_key and client is None:
            raise ValueError("OPENAI_API_KEY is required to scan sources")
        self.settings = settings
        self.client = client or OpenAI(api_key=settings.openai_api_key)

    def scan(self, source: Source, start_date: date, end_date: date) -> ScannedSourceResult:
        response = self.client.responses.create(
            model=self.settings.openai_model,
            instructions=SCANNER_INSTRUCTIONS,
            input=build_scan_prompt(source, start_date, end_date),
            tools=[
                {
                    "type": "web_search",
                    "filters": {"allowed_domains": [source.domain]},
                    "search_context_size": "medium",
                }
            ],
            include=["web_search_call.action.sources"],
            max_tool_calls=self.settings.openai_max_tool_calls,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "source_scan_result",
                    "strict": True,
                    "schema": SOURCE_SCAN_SCHEMA,
                }
            },
            store=False,
        )
        result = SourceScanResult.model_validate(json.loads(response.output_text))
        result.items = [
            item for item in result.items if _belongs_to_domain(str(item.url), source.domain)
        ]
        return ScannedSourceResult(result=result, response_id=getattr(response, "id", None))


def _belongs_to_domain(url: str, domain: str) -> bool:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    expected = domain.lower().rstrip(".")
    return host == expected or host.endswith(f".{expected}")
