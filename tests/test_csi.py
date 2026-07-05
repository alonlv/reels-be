import base64

import app.ingest.link as link_mod
import app.routers.feed as feed_mod


def _stub_fetch(monkeypatch, **meta):
    base = {"title": None, "image_url": None, "summary": None, "text": None}
    base.update(meta)
    monkeypatch.setattr(link_mod, "fetch_metadata", lambda url: base)


def test_csi_creates_item_with_photo(client):
    png = base64.b64encode(b"\x89PNG\r\n\x1a\nfakebytes").decode()
    resp = client.post(
        "/api/csi",
        data={"title": "Field report", "summary": "what we saw", "link": ""},
        files={"photo": ("shot.png", base64.b64decode(png), "image/png")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["feed"] == "csi"
    assert body["title"] == "Field report"
    assert body["short_summary"] == "what we saw"
    assert body["image_data"].startswith("data:image/png;base64,")
    # No LLM requested → no long blurb.
    assert body["long_summary"] is None


def test_csi_requires_title(client):
    resp = client.post("/api/csi", data={"title": "  ", "summary": "x"})
    assert resp.status_code == 400


def test_csi_uses_llm_when_checked(client, monkeypatch):
    class FakeProvider:
        def explain(self, title, text):
            return {"short": "llm short", "long": "llm long", "category": "research"}

    monkeypatch.setattr(feed_mod, "get_provider", lambda: FakeProvider())
    # Enrichment is async in production; run it inline so the test is deterministic.
    monkeypatch.setattr(feed_mod, "_enrich_in_background", feed_mod._enrich_and_update)
    resp = client.post(
        "/api/csi",
        data={"title": "Deep topic", "summary": "seed", "use_llm": "true"},
    )
    assert resp.status_code == 201
    item_id = resp.json()["id"]
    got = next(i for i in client.get("/api/feed?feed=csi").json() if i["id"] == item_id)
    assert got["short_summary"] == "llm short"
    assert got["long_summary"] == "llm long"
    assert got["category"] == "research"


def test_csi_llm_does_not_block_the_request(client, monkeypatch):
    # The request must return before the (slow) model runs — assert it hands the
    # work to the background helper rather than calling enrich inline.
    calls = {}
    monkeypatch.setattr(
        feed_mod, "_enrich_in_background",
        lambda *a: calls.setdefault("args", a),
    )
    resp = client.post(
        "/api/csi",
        data={"title": "Async topic", "summary": "seed text", "use_llm": "true"},
    )
    assert resp.status_code == 201
    # Response carries the user's seed immediately; enrichment deferred.
    assert resp.json()["short_summary"] == "seed text"
    assert resp.json()["long_summary"] is None
    assert calls["args"][1] == "Async topic"


def test_csi_rejects_bad_link(client):
    resp = client.post("/api/csi", data={"title": "T", "link": "ftp://nope"})
    assert resp.status_code == 400


def test_csi_rejects_unverifiable_public_link(client, monkeypatch):
    # Same rule as the submit flow: a public link that won't load is rejected.
    _stub_fetch(monkeypatch)  # all-None → not reachable
    resp = client.post(
        "/api/csi",
        data={"title": "T", "link": "https://example.com/gone"},
    )
    assert resp.status_code == 400
    assert "verify" in resp.json()["detail"].lower()


def test_csi_keeps_non_public_link_without_fetching(client, monkeypatch):
    # Internal links are the common CSI case — never fetched, never rejected.
    def _boom(url):
        raise AssertionError("must not fetch a non-public link")

    monkeypatch.setattr(link_mod, "fetch_metadata", _boom)
    resp = client.post(
        "/api/csi",
        data={"title": "Internal report", "link": "http://intranet.corp/report/1"},
    )
    assert resp.status_code == 201
    assert resp.json()["source_url"] == "http://intranet.corp/report/1"


def test_csi_backfills_from_verified_public_link(client, monkeypatch):
    # A verified link backfills the summary/image and feeds the model its text.
    _stub_fetch(
        monkeypatch, title="Page", summary="extracted blurb",
        image_url="https://img/x.png", text="full extracted body",
    )
    seen = {}

    class FakeProvider:
        def explain(self, title, text):
            seen["text"] = text
            return {"short": "llm short", "long": "llm long", "category": "product"}

    monkeypatch.setattr(feed_mod, "get_provider", lambda: FakeProvider())
    monkeypatch.setattr(feed_mod, "_enrich_in_background", feed_mod._enrich_and_update)
    resp = client.post(
        "/api/csi",
        data={"title": "Deep", "link": "https://example.com/a", "use_llm": "true"},
    )
    assert resp.status_code == 201
    body = resp.json()
    # No user summary → extracted blurb backfills it; no photo → og:image used.
    assert body["image_url"] == "https://img/x.png"
    # The model was handed the extracted page body.
    assert seen["text"] == "full extracted body"


def test_csi_hidden_from_ai_news_feed(client):
    client.post("/api/csi", data={"title": "CSI only", "summary": "s"})
    ai = client.get("/api/feed?feed=ai_news").json()
    csi = client.get("/api/feed?feed=csi").json()
    assert all(i["feed"] == "ai_news" for i in ai)
    assert any(i["title"] == "CSI only" for i in csi)
