import app.routers.feed as feed_mod


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
