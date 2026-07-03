import json
from pathlib import Path

from app.db import SessionLocal
from app.models import Source

CONFIG = Path(__file__).resolve().parents[2] / "sources.config.json"


def sync_sources() -> None:
    if not CONFIG.exists():
        return
    entries = json.loads(CONFIG.read_text())
    with SessionLocal() as s:
        for e in entries:
            existing = s.query(Source).filter_by(url=e["url"]).first()
            if existing:
                existing.kind = e["kind"]
                existing.name = e["name"]
            else:
                s.add(Source(kind=e["kind"], name=e["name"], url=e["url"]))
        s.commit()
