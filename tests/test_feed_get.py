from app.models import FeedItem
import app.db as db


def _make(session, **kw):
    defaults = dict(
        content_type="article", source_url="https://e.com/x",
        dedup_hash="h", source_type="manual",
        shared_by_name="A", shared_by_email="a@x.com",
    )
    defaults.update(kw)
    session.add(FeedItem(**defaults))


def test_feed_sorts_by_views(client):
    with db.SessionLocal() as s:
        _make(s, dedup_hash="a", views=1, title="low")
        _make(s, dedup_hash="b", views=9, title="high")
        s.commit()
    resp = client.get("/api/feed?sort_by=views")
    assert resp.status_code == 200
    titles = [r["title"] for r in resp.json()]
    assert titles == ["high", "low"]


def test_feed_excludes_draft(client):
    with db.SessionLocal() as s:
        _make(s, dedup_hash="d", status="draft", title="hidden")
        s.commit()
    resp = client.get("/api/feed")
    assert resp.status_code == 200
    assert resp.json() == []
