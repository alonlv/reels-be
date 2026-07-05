import app.routers.sources as sources_mod


def test_list_add_delete_source(client, monkeypatch):
    # Don't actually kick a scan during the test.
    monkeypatch.setattr(sources_mod.threading, "Thread", lambda *a, **k: type(
        "T", (), {"start": lambda self: None})())

    assert client.get("/api/sources").json() == []

    resp = client.post("/api/sources", json={
        "name": "My Feed", "url": "https://example.com/rss.xml",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "My Feed"
    assert body["kind"] == "rss"
    assert body["is_active"] is True

    listed = client.get("/api/sources").json()
    assert len(listed) == 1

    assert client.delete(f"/api/sources/{body['id']}").status_code == 204
    assert client.get("/api/sources").json() == []


def test_add_source_rejects_bad_url(client):
    resp = client.post("/api/sources", json={"name": "x", "url": "not-a-url"})
    assert resp.status_code == 400


def test_add_duplicate_url_reactivates(client, monkeypatch):
    monkeypatch.setattr(sources_mod.threading, "Thread", lambda *a, **k: type(
        "T", (), {"start": lambda self: None})())
    url = "https://example.com/dup.xml"
    first = client.post("/api/sources", json={"name": "A", "url": url}).json()
    second = client.post("/api/sources", json={"name": "B", "url": url}).json()
    assert first["id"] == second["id"]
    assert second["name"] == "B"
    assert len(client.get("/api/sources").json()) == 1
