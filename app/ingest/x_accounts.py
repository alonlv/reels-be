import json
from pathlib import Path

import app.db as db
from app.models import MonitoredXAccount

CONFIG = Path(__file__).resolve().parents[2] / "x_accounts.config.json"


def sync_x_accounts() -> None:
    if not CONFIG.exists():
        return
    entries = json.loads(CONFIG.read_text())
    with db.SessionLocal() as s:
        for e in entries:
            existing = s.query(MonitoredXAccount).filter_by(x_handle=e["x_handle"]).first()
            if existing:
                existing.x_user_id = e["x_user_id"]
            else:
                s.add(MonitoredXAccount(
                    x_handle=e["x_handle"], x_user_id=e["x_user_id"], is_active=True,
                ))
        s.commit()
