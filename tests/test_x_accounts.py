import json

import app.ingest.x_accounts as xa
import app.db as db
from app.models import MonitoredXAccount


def test_sync_x_accounts_creates_then_updates(session_factory, monkeypatch, tmp_path):
    config = tmp_path / "x_accounts.config.json"
    config.write_text(json.dumps([
        {"x_handle": "OpenAI", "x_user_id": "111"},
        {"x_handle": "GoogleAI", "x_user_id": "222"},
    ]))
    monkeypatch.setattr(xa, "CONFIG", config)

    xa.sync_x_accounts()

    with db.SessionLocal() as s:
        rows = s.query(MonitoredXAccount).order_by(MonitoredXAccount.x_handle).all()
        assert [r.x_handle for r in rows] == ["GoogleAI", "OpenAI"]
        assert {r.x_user_id for r in rows} == {"111", "222"}
        assert all(r.is_active for r in rows)

    # Re-running with an updated id should update in place, not duplicate.
    config.write_text(json.dumps([
        {"x_handle": "OpenAI", "x_user_id": "999"},
        {"x_handle": "GoogleAI", "x_user_id": "222"},
    ]))
    xa.sync_x_accounts()

    with db.SessionLocal() as s:
        rows = s.query(MonitoredXAccount).all()
        assert len(rows) == 2
        openai = s.query(MonitoredXAccount).filter_by(x_handle="OpenAI").first()
        assert openai.x_user_id == "999"


def test_sync_x_accounts_missing_config_is_noop(session_factory, monkeypatch, tmp_path):
    monkeypatch.setattr(xa, "CONFIG", tmp_path / "does_not_exist.json")
    xa.sync_x_accounts()
    with db.SessionLocal() as s:
        assert s.query(MonitoredXAccount).count() == 0
