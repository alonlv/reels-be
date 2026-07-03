import app.routers.feed as feed_mod


def test_scan_route_triggers(client, monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(feed_mod, "run_scan", lambda: called.__setitem__("n", 1))
    resp = client.post("/api/scan")
    assert resp.status_code == 202
    assert resp.json() == {"ok": True}
