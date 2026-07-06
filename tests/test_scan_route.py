import app.routers.feed as feed_mod

ADMIN = {"X-Admin-Token": "admin"}


def test_scan_route_triggers(client, monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(feed_mod, "run_scan", lambda: called.__setitem__("n", 1))
    resp = client.post("/api/scan", headers=ADMIN)
    assert resp.status_code == 202
    assert resp.json() == {"ok": True}


def test_scan_route_requires_admin(client):
    assert client.post("/api/scan").status_code == 403