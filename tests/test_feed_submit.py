from sqlalchemy.orm import Session

import app.db as db
import app.routers.feed as feed_mod
from app.models import FeedItem


def test_submit_creates_published_item(client, monkeypatch):
    monkeypatch.setattr(
        feed_mod, "fetch_metadata",
        lambda url: {"title": "T", "image_url": "https://i/x.png", "summary": "S"},
    )
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


def test_submit_duplicate_409(client, monkeypatch):
    monkeypatch.setattr(
        feed_mod, "fetch_metadata",
        lambda url: {"title": "T", "image_url": None, "summary": None},
    )
    payload = {"url": "https://example.com/dup", "title": "Same"}
    assert client.post("/api/feed", json=payload).status_code == 201
    assert client.post("/api/feed", json=payload).status_code == 409


def test_submit_duplicate_race_returns_409(client, monkeypatch):
    """Two concurrent submits can both pass the fast pre-check and only fail
    on the unique dedup_hash constraint at insert time. Simulate that race by
    bypassing the pre-check (making it see no match) while the row already
    exists, so the request falls through to the IntegrityError -> 409 path.
    """
    monkeypatch.setattr(
        feed_mod, "fetch_metadata",
        lambda url: {"title": "T", "image_url": None, "summary": None},
    )
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
