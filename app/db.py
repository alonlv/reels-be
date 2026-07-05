from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def migrate() -> None:
    import app.models  # noqa: F401 — register mappers before create_all
    engine = get_engine()
    _heal_legacy_sources(engine)
    Base.metadata.create_all(engine)
    # create_all() never ALTERs an existing table, so newly added columns won't
    # appear on a database created by an earlier app version. Add them in place.
    _add_missing_columns(engine, "feed_items", {
        "short_summary": "TEXT",
        "long_summary": "TEXT",
        "category": "VARCHAR(32)",
        "feed": "VARCHAR(16) DEFAULT 'ai_news'",
        "image_data": "TEXT",
    })


def _add_missing_columns(engine: Engine, table: str, columns: dict[str, str]) -> None:
    """Add any of ``columns`` (name -> SQL type) missing from ``table``."""
    inspector = inspect(engine)
    if not inspector.has_table(table):
        return
    existing = {c["name"] for c in inspector.get_columns(table)}
    missing = {n: ddl for n, ddl in columns.items() if n not in existing}
    if not missing:
        return
    with engine.begin() as conn:
        for name, ddl in missing.items():
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def _heal_legacy_sources(engine: Engine) -> None:
    """Drop a drifted legacy `sources` table so create_all can rebuild it.

    An earlier app version (the old Node monolith) created a `sources` table
    with a different schema against this same database. create_all() never
    alters an existing table, so the stale table keeps its old columns and
    queries for new ones (e.g. `kind`) fail on boot. The `sources` table is a
    cache repopulated from sources.config.json on every startup, so if it
    exists but is missing any current column we drop it and recreate it.
    """
    import app.models

    inspector = inspect(engine)
    if not inspector.has_table("sources"):
        return
    existing = {c["name"] for c in inspector.get_columns("sources")}
    required = {c.name for c in app.models.Source.__table__.columns}
    if not required.issubset(existing):
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE sources CASCADE"))
