from app.models import FeedItem
import app.db as db


def _seed(dedup="a", **kw):
    with db.SessionLocal() as s:
        defaults = dict(
            content_type="article", source_url="https://e.com/x", dedup_hash=dedup,
            source_type="auto", status="published", shared_by_name="Sys",
            shared_by_email="s@x.com", title="Old title", short_summary="old",
        )
        defaults.update(kw)
        item = FeedItem(**defaults)
        s.add(item)
        s.commit()
        return item.id


def test_login_guest_and_admin(client):
    guest = client.post("/api/login", json={"username": "Alice"}).json()
    assert guest["role"] == "guest"
    assert guest["token"] is None

    admin = client.post("/api/login", json={"username": "Boss", "password": "admin"})
    body = admin.json()
    assert body["role"] == "admin"
    assert body["token"] == "admin"

    bad = client.post("/api/login", json={"username": "x", "password": "nope"})
    assert bad.status_code == 401


def test_edit_requires_admin_token(client):
    fid = _seed("edit1")
    # No token → forbidden.
    assert client.patch(f"/api/feed/{fid}", json={"title": "New"}).status_code == 403
    # Wrong token → forbidden.
    resp = client.patch(
        f"/api/feed/{fid}", json={"title": "New"},
        headers={"X-Admin-Token": "wrong"},
    )
    assert resp.status_code == 403


def test_admin_can_edit_reel(client):
    fid = _seed("edit2")
    resp = client.patch(
        f"/api/feed/{fid}",
        json={"title": "Edited", "short_summary": "new short",
              "technical_summary": "the specs", "category": "product"},
        headers={"X-Admin-Token": "admin"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Edited"
    assert body["short_summary"] == "new short"
    assert body["article_summary"] == "new short"  # kept in sync
    assert body["technical_summary"] == "the specs"
    assert body["category"] == "product"


def test_admin_can_delete_reel(client):
    fid = _seed("del1")
    assert client.delete(f"/api/feed/{fid}").status_code == 403
    resp = client.delete(f"/api/feed/{fid}", headers={"X-Admin-Token": "admin"})
    assert resp.status_code == 204
    assert client.get("/api/feed").json() == []
