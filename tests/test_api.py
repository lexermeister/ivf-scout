from fastapi.testclient import TestClient

from ivf_scout.api import app, get_session
from ivf_scout.db.models import Source


def _client(session):
    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def _payload():
    return {
        "name": "Example Fertility",
        "slug": "example-fertility",
        "domain": "example.com",
        "website_url": "https://www.example.com/",
        "news_url": "https://news.example.com/announcements/",
        "article_url_patterns": ["/announcements/"],
        "enabled": True,
    }


def test_create_source(session):
    with _client(session) as client:
        response = client.post("/sources", json=_payload())
    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["slug"] == "example-fertility"
    assert response.json()["scan_query"].startswith("any newly introduced")
    assert session.query(Source).one().news_url == "https://news.example.com/announcements/"


def test_create_source_rejects_duplicate_slug(session):
    with _client(session) as client:
        first = client.post("/sources", json=_payload())
        second = client.post("/sources", json=_payload())
    app.dependency_overrides.clear()

    assert first.status_code == 201
    assert second.status_code == 409


def test_create_source_rejects_url_outside_domain(session):
    payload = _payload()
    payload["news_url"] = "https://malicious.example.net/news/"

    with _client(session) as client:
        response = client.post("/sources", json=payload)
    app.dependency_overrides.clear()

    assert response.status_code == 422
    assert session.query(Source).count() == 0


def test_create_source_rejects_ip_address_domain(session):
    payload = _payload()
    payload.update(
        domain="127.0.0.1",
        website_url="http://127.0.0.1/",
        news_url="http://127.0.0.1/news/",
    )

    with _client(session) as client:
        response = client.post("/sources", json=payload)
    app.dependency_overrides.clear()

    assert response.status_code == 422
    assert session.query(Source).count() == 0
