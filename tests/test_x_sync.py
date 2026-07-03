import app.ingest.x_sync as xs
from app.models import MonitoredXAccount, FeedItem
import app.db as db


def test_sync_account_inserts_and_updates_last_id(session_factory, monkeypatch):
    monkeypatch.setattr(xs, "fetch_tweets", lambda uid, since, bearer: [
        {"id": "100", "text": "newer tweet"},
        {"id": "99", "text": "older tweet"},
    ])
    with db.SessionLocal() as s:
        acct = MonitoredXAccount(x_handle="@ai", x_user_id="1", is_active=True)
        s.add(acct); s.commit()
        n = xs.sync_account(s, acct, "bearer")
        assert n == 2
        assert acct.last_tweet_id == "100"
        items = s.query(FeedItem).all()
        assert all(i.content_type == "x" for i in items)
        assert all(i.shared_by_name == "System Auto-Pull" for i in items)


def test_run_x_sync_noop_without_token(session_factory, monkeypatch):
    from app.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("X_BEARER_TOKEN", "")
    assert xs.run_x_sync() == 0
