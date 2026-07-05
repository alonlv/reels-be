from sqlalchemy.orm import Session

import app.db as db
import app.ingest.link as link_mod
import app.routers.feed as feed_mod
from app.models import FeedItem


def _stub_fetch(monkeypatch, **meta):
    """Point the link inspector's fetch at a fixed metadata dict."""
    base = {"title": None, "image_url": None, "summary": None, "text": None}
    base.update(meta)
    monkeypatch.setattr(link_mod, "fetch_metadata", lambda url: base)


def test_submit_creates_published_item(client, monkeypatch):
    _stub_fetch(monkeypatch, title="T", image_url="https://i/x.png", summary="S")
    resp = client.post("/api/feed", json={
        "url": "https://youtu.be/abc", "shared_by_name": "Bob",
        "shared_by_email": "bob@x.com",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["content_type"] == "youtube"
    assert body["status"] == "published"
    assert body["source_type"] == "manual"
    assert body["title"] == "T"


def test_submit_rejects_bad_url(client):
    resp = client.post("/api/feed", json={"url": "ftp://nope"})
    assert resp.status_code == 400


def test_submit_rejects_unverifiable_public_link(client, monkeypatch):
    # A public URL that returns nothing usable is dead/blocked — don't store it.
    _stub_fetch(monkeypatch)  # all-None metadata
    resp = client.post("/api/feed", json={"url": "https://example.com/gone"})
    assert resp.status_code == 400
    assert "verify" in resp.json()["detail"].lower()


def test_submit_accepts_platform_link_that_blocks_scrapers(client, monkeypatch):
    # YouTube/X/Reddit render from their embed even when the metadata fetch is
    # blocked (403) — an unreachable fetch there must NOT reject the submission.
    _stub_fetch(monkeypatch)  # all-None → unreachable
    resp = client.post("/api/feed", json={"url": "https://youtu.be/xyz"})
    assert resp.status_code == 201
    assert resp.json()["content_type"] == "youtube"


def test_submit_keeps_non_public_link_unverified(client, monkeypatch):
    # An internal host can't be reached, so we never fetch it and never reject.
    def _boom(url):
        raise AssertionError("must not fetch a non-public link")

    monkeypatch.setattr(link_mod, "fetch_metadata", _boom)
    resp = client.post("/api/feed", json={"url": "http://wiki.corp/page"})
    assert resp.status_code == 201
    body = resp.json()
    # Nothing extractable → the URL stands in for the title.
    assert body["title"] == "http://wiki.corp/page"


def test_submit_runs_llm_when_summarize_true(client, monkeypatch):
    _stub_fetch(monkeypatch, title="T", summary="raw page text")

    class FakeProvider:
        def explain(self, title, text):
            return {"short": "AI short", "long": "AI long", "category": "product"}

    monkeypatch.setattr(feed_mod, "get_provider", lambda: FakeProvider())
    # Enrichment runs in a background thread; run it inline for the test.
    monkeypatch.setattr(feed_mod, "_enrich_in_background", feed_mod._enrich_and_update)
    resp = client.post("/api/feed", json={
        "url": "https://example.com/p", "summarize": True,
    })
    assert resp.status_code == 201
    item_id = resp.json()["id"]
    got = next(i for i in client.get("/api/feed").json() if i["id"] == item_id)
    assert got["short_summary"] == "AI short"
    assert got["long_summary"] == "AI long"
    assert got["category"] == "product"
    assert got["feed"] == "ai_news"


def test_submit_feeds_extracted_text_to_the_model(client, monkeypatch):
    # "See what can be extracted from it": the model must receive the page body,
    # not just the URL or a short blurb.
    _stub_fetch(monkeypatch, title="T", summary="short blurb",
                text="the full extracted article body")
    seen = {}

    class FakeProvider:
        def explain(self, title, text):
            seen["text"] = text
            return {"short": "s", "long": "l", "category": "research"}

    monkeypatch.setattr(feed_mod, "get_provider", lambda: FakeProvider())
    monkeypatch.setattr(feed_mod, "_enrich_in_background", feed_mod._enrich_and_update)
    resp = client.post("/api/feed", json={
        "url": "https://example.com/article", "summarize": True,
    })
    assert resp.status_code == 201
    assert seen["text"] == "the full extracted article body"


def test_submit_duplicate_409(client, monkeypatch):
    _stub_fetch(monkeypatch, title="T")
    payload = {"url": "https://example.com/dup", "title": "Same"}
    assert client.post("/api/feed", json=payload).status_code == 201
    assert client.post("/api/feed", json=payload).status_code == 409


def test_submit_duplicate_race_returns_409(client, monkeypatch):
    """Two concurrent submits can both pass the fast pre-check and only fail
    on the unique dedup_hash constraint at insert time. Simulate that race by
    bypassing the pre-check (making it see no match) while the row already
    exists, so the request falls through to the IntegrityError -> 409 path.
    """
    _stub_fetch(monkeypatch, title="T")
    payload = {"url": "https://example.com/race", "title": "Race"}
    h = feed_mod.dedup_hash(payload["url"], payload["title"])
    with db.SessionLocal() as s:
        s.add(FeedItem(
            content_type="link", source_url=payload["url"], dedup_hash=h,
            title=payload["title"], source_type="manual", status="published",
            shared_by_name="Existing", shared_by_email="e@x.com",
        ))
        s.commit()

    class _EmptyQuery:
        def filter_by(self, **kwargs):
            return self

        def first(self):
            return None

    monkeypatch.setattr(Session, "query", lambda self, *a, **k: _EmptyQuery())

    resp = client.post("/api/feed", json=payload)
    assert resp.status_code == 409
