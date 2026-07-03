from app.models import FeedItem
import app.db as db


def _seed(dedup="e"):
    with db.SessionLocal() as s:
        item = FeedItem(
            content_type="article", source_url="https://e.com/x",
            dedup_hash=dedup, source_type="manual",
            shared_by_name="A", shared_by_email="a@x.com",
            views=0, likes=0,
        )
        s.add(item)
        s.commit()
        return item.id


def test_view_increments(client):
    fid = _seed("v")
    r1 = client.post(f"/api/feed/{fid}/view")
    r2 = client.post(f"/api/feed/{fid}/view")
    assert r1.json()["views"] == 1
    assert r2.json()["views"] == 2


def test_like_increments(client):
    fid = _seed("l")
    r = client.post(f"/api/feed/{fid}/like")
    assert r.json()["likes"] == 1


def test_view_missing_404(client):
    assert client.post("/api/feed/99999/view").status_code == 404
