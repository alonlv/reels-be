import app.routers.sources as sources_mod

# Managing feeds is admin-only; the test admin password is "admin".
ADMIN = {"X-Admin-Token": "admin"}


def test_list_add_delete_source(client, monkeypatch):
    # Don't actually kick a scan during the test.
    monkeypatch.setattr(sources_mod.threading, "Thread", lambda *a, **k: type(
        "T", (), {"start": lambda self: None})())

    assert client.get("/api/sources").json() == []

    resp = client.post("/api/sources", json={
        "name": "My Feed", "url": "https://example.com/rss.xml",
    }, headers=ADMIN)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "My Feed"
    assert body["kind"] == "rss"
    assert body["is_active"] is True

    listed = client.get("/api/sources").json()
    assert len(listed) == 1

    assert client.delete(f"/api/sources/{body['id']}", headers=ADMIN).status_code == 204
    assert client.get("/api/sources").json() == []


def test_add_source_requires_admin(client):
    # No token / wrong token → forbidden; listing stays open to everyone.
    assert client.post("/api/sources", json={
        "name": "x", "url": "https://e.com/f.xml",
    }).status_code == 403
    assert client.post("/api/sources", json={
        "name": "x", "url": "https://e.com/f.xml",
    }, headers={"X-Admin-Token": "nope"}).status_code == 403
    assert client.get("/api/sources").json() == []


def test_delete_source_requires_admin(client, monkeypatch):
    monkeypatch.setattr(sources_mod.threading, "Thread", lambda *a, **k: type(
        "T", (), {"start": lambda self: None})())
    made = client.post("/api/sources", json={
        "name": "A", "url": "https://e.com/a.xml",
    }, headers=ADMIN).json()
    assert client.delete(f"/api/sources/{made['id']}").status_code == 403


def test_add_source_rejects_bad_url(client):
    resp = client.post("/api/sources", json={
        "name": "x", "url": "not-a-url",
    }, headers=ADMIN)
    assert resp.status_code == 400


def test_add_duplicate_url_reactivates(client, monkeypatch):
    monkeypatch.setattr(sources_mod.threading, "Thread", lambda *a, **k: type(
        "T", (), {"start": lambda self: None})())
    url = "https://example.com/dup.xml"
    first = client.post("/api/sources", json={"name": "A", "url": url}, headers=ADMIN).json()
    second = client.post("/api/sources", json={"name": "B", "url": url}, headers=ADMIN).json()
    assert first["id"] == second["id"]
    assert second["name"] == "B"
    assert len(client.get("/api/sources").json()) == 1
