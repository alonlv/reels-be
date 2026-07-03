# Reels BE/FE Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the existing Express+React monolith into a Python/FastAPI backend (`reels-be`) and a rebuilt React/Vite reels-style frontend (`reels-fe`), backed by a local Ollama `gemma2:2b` model.

**Architecture:** Two independent git repos talking over HTTP. Backend owns Postgres and exposes `/api/*` REST with CORS; APScheduler runs X.com + RSS ingestion inside the FastAPI lifespan. Frontend is a full-screen scroll-snap feed reading `VITE_API_BASE_URL`. Local dev via one docker-compose (Ollama on host).

**Tech Stack:** Backend — Python 3.11, FastAPI, SQLAlchemy 2.0, pydantic-settings, APScheduler, feedparser, BeautifulSoup4, httpx, pytest. Frontend — React 18, Vite 6, TypeScript, vitest. Orchestration — Docker, docker-compose, Postgres 16.

## Global Constraints

- Backend Python `>=3.11`. Frontend Node `>=20`.
- Default LLM: `MODEL_PROVIDER=ollama`, `OLLAMA_MODEL=gemma2:2b`, `OLLAMA_BASE_URL=http://host.docker.internal:11434`. Providers also selectable: `anthropic`, `openai`.
- `content_type` is exactly one of: `youtube | x | reddit | article`.
- `source_type` is exactly one of: `auto | manual`. `status` is exactly one of: `draft | published`.
- Auto content (X + RSS) inserts as `status='published'`. X auto-pull uses `shared_by_name='System Auto-Pull'`, `shared_by_email='system@company.internal'`.
- All REST routes are under `/api`. Sorting param `sort_by` ∈ `date | views | likes` (default `date`).
- LLM is used ONLY by the RSS/HTML scanner. On LLM error/timeout, fall back to the raw OG description — never crash a scan.
- Duplicate inserts prevented by a unique `dedup_hash`; ingestion uses insert-or-ignore.
- Backend working dir: `/Users/levy/Code/reels/reels-be`. Frontend working dir: `/Users/levy/Code/reels/reels-fe`.

---

## Phase A — Backend (reels-be)

Run all Phase A commands from `/Users/levy/Code/reels/reels-be`.

### Task A1: Project scaffold + health endpoint

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py` (empty)
- Create: `app/config.py`
- Create: `app/main.py`
- Create: `tests/__init__.py` (empty)
- Create: `tests/conftest.py`
- Test: `tests/test_health.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `app.main.create_app() -> FastAPI`; `app.config.Settings` (pydantic-settings) with fields `database_url: str`, `model_provider: str = "ollama"`, `ollama_base_url: str`, `ollama_model: str = "gemma2:2b"`, `anthropic_api_key: str | None`, `openai_api_key: str | None`, `cors_origins: str = "*"`, `rate_limit_max: int = 5`, `scan_cron: str = "0 */6 * * *"`, `x_sync_interval_hours: int = 6`, `x_bearer_token: str | None`, `scan_enabled: bool = True`; `app.config.get_settings() -> Settings` (cached).

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "reels-be"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.110",
  "uvicorn[standard]>=0.29",
  "sqlalchemy>=2.0",
  "psycopg2-binary>=2.9",
  "pydantic-settings>=2.2",
  "apscheduler>=3.10",
  "httpx>=0.27",
  "feedparser>=6.0",
  "beautifulsoup4>=4.12",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[tool.pytest.ini_options]
pythonpath = ["."]
```

- [ ] **Step 2: Write `app/config.py`**

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./reels.db"
    model_provider: str = "ollama"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "gemma2:2b"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-4-8"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    cors_origins: str = "*"
    rate_limit_max: int = 5
    scan_cron: str = "0 */6 * * *"
    x_sync_interval_hours: int = 6
    x_bearer_token: str | None = None
    scan_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 3: Write `app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="reels-be")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    return app


app = create_app()
```

- [ ] **Step 4: Write `tests/conftest.py`**

```python
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    return TestClient(create_app())
```

- [ ] **Step 5: Write the failing test `tests/test_health.py`**

```python
def test_health_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
```

- [ ] **Step 6: Install deps and run test to verify it passes**

Run:
```bash
python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
pytest tests/test_health.py -v
```
Expected: PASS.

- [ ] **Step 7: Write `.gitignore` and `.env.example`**

`.gitignore`:
```
.venv/
__pycache__/
*.db
.env
```

`.env.example`:
```
DATABASE_URL=postgresql+psycopg2://reels:reels@localhost:5432/reels
MODEL_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=gemma2:2b
# ANTHROPIC_API_KEY=
# OPENAI_API_KEY=
CORS_ORIGINS=http://localhost:5173
SCAN_ENABLED=true
SCAN_CRON=0 */6 * * *
X_SYNC_INTERVAL_HOURS=6
# X_BEARER_TOKEN=
```

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml app tests .gitignore .env.example
git commit -m "feat(be): scaffold FastAPI app with health endpoint and settings"
```

---

### Task A2: DB layer + models + migrate

**Files:**
- Create: `app/db.py`
- Create: `app/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: `app.config.get_settings`.
- Produces:
  - `app.db.Base` (SQLAlchemy `DeclarativeBase`).
  - `app.db.get_engine()` — cached engine from `settings.database_url`.
  - `app.db.SessionLocal` — sessionmaker; `app.db.get_session()` FastAPI dependency yielding a `Session`.
  - `app.db.migrate()` — `Base.metadata.create_all(get_engine())`.
  - `app.models.FeedItem` with columns: `id:int PK`, `content_type:str`, `source_url:str`, `dedup_hash:str unique`, `title:str|None`, `author:str|None`, `article_summary:str|None`, `image_url:str|None`, `source_type:str`, `status:str default 'published'`, `shared_by_name:str`, `shared_by_email:str`, `views:int default 0`, `likes:int default 0`, `created_at:datetime server_default now`.
  - `app.models.MonitoredXAccount`: `id PK`, `x_handle:str unique`, `x_user_id:str`, `last_tweet_id:str|None`, `is_active:bool default True`.
  - `app.models.Source`: `id PK`, `kind:str` (rss|html|reddit), `name:str`, `url:str unique`, `is_active:bool default True`.

- [ ] **Step 1: Write `app/db.py`**

```python
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine
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
    Base.metadata.create_all(get_engine())
```

- [ ] **Step 2: Write `app/models.py`**

```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class FeedItem(Base):
    __tablename__ = "feed_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_type: Mapped[str] = mapped_column(String(16))
    source_url: Mapped[str] = mapped_column(String(2048))
    dedup_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    author: Mapped[str | None] = mapped_column(String(256), nullable=True)
    article_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_type: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="published")
    shared_by_name: Mapped[str] = mapped_column(String(256))
    shared_by_email: Mapped[str] = mapped_column(String(256))
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class MonitoredXAccount(Base):
    __tablename__ = "monitored_x_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    x_handle: Mapped[str] = mapped_column(String(64), unique=True)
    x_user_id: Mapped[str] = mapped_column(String(64))
    last_tweet_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(256))
    url: Mapped[str] = mapped_column(String(2048), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
```

- [ ] **Step 3: Update `tests/conftest.py` to use an isolated SQLite DB + migrated schema**

Replace the file contents with:
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.db as db
from app.db import Base


@pytest.fixture
def session_factory(tmp_path):
    url = f"sqlite:///{tmp_path/'test.db'}"
    engine = create_engine(url, connect_args={"check_same_thread": False}, future=True)
    import app.models  # noqa: F401
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    # Point the app's SessionLocal at this test engine.
    db.SessionLocal = factory
    return factory


@pytest.fixture
def client(session_factory):
    from app.main import create_app
    return TestClient(create_app())
```

- [ ] **Step 4: Write the failing test `tests/test_models.py`**

```python
from app.models import FeedItem


def test_feeditem_defaults(session_factory):
    with session_factory() as s:
        item = FeedItem(
            content_type="article",
            source_url="https://example.com/a",
            dedup_hash="h1",
            source_type="manual",
            shared_by_name="Alice",
            shared_by_email="alice@x.com",
        )
        s.add(item)
        s.commit()
        s.refresh(item)
        assert item.id is not None
        assert item.views == 0
        assert item.likes == 0
        assert item.status == "published"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/db.py app/models.py tests/conftest.py tests/test_models.py
git commit -m "feat(be): add SQLAlchemy models and DB layer"
```

---

### Task A3: dedupe + classify utilities

**Files:**
- Create: `app/ingest/__init__.py` (empty)
- Create: `app/ingest/dedupe.py`
- Create: `app/ingest/classify.py`
- Test: `tests/test_ingest_utils.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `app.ingest.dedupe.dedup_hash(url: str | None, title: str | None) -> str` — sha256 hex of `f"{url or ''}|{(title or '').strip().lower()}"`.
  - `app.ingest.classify.classify_url(url: str) -> str` — returns `youtube | x | reddit | article`.

- [ ] **Step 1: Write the failing test `tests/test_ingest_utils.py`**

```python
from app.ingest.dedupe import dedup_hash
from app.ingest.classify import classify_url


def test_dedup_hash_stable_and_case_insensitive_title():
    a = dedup_hash("https://e.com/x", "Hello World")
    b = dedup_hash("https://e.com/x", "hello world")
    assert a == b
    assert len(a) == 64


def test_classify_url():
    assert classify_url("https://www.youtube.com/watch?v=abc") == "youtube"
    assert classify_url("https://youtu.be/abc") == "youtube"
    assert classify_url("https://twitter.com/foo/status/1") == "x"
    assert classify_url("https://x.com/foo/status/1") == "x"
    assert classify_url("https://www.reddit.com/r/ml/comments/1/x") == "reddit"
    assert classify_url("https://example.com/blog/post") == "article"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingest_utils.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/ingest/dedupe.py`**

```python
import hashlib


def dedup_hash(url: str | None, title: str | None) -> str:
    basis = f"{url or ''}|{(title or '').strip().lower()}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Write `app/ingest/classify.py`**

```python
from urllib.parse import urlparse


def classify_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    if host in {"youtube.com", "youtu.be", "m.youtube.com"}:
        return "youtube"
    if host in {"twitter.com", "x.com", "mobile.twitter.com"}:
        return "x"
    if host in {"reddit.com", "old.reddit.com"} or host.endswith(".reddit.com"):
        return "reddit"
    return "article"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_ingest_utils.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/ingest tests/test_ingest_utils.py
git commit -m "feat(be): add dedup hashing and URL content-type classifier"
```

---

### Task A4: Feed schemas + GET /api/feed with sorting

**Files:**
- Create: `app/schemas.py`
- Create: `app/routers/__init__.py` (empty)
- Create: `app/routers/feed.py`
- Modify: `app/main.py` (mount feed router)
- Test: `tests/test_feed_get.py`

**Interfaces:**
- Consumes: `app.db.get_session`, `app.models.FeedItem`.
- Produces:
  - `app.schemas.FeedItemOut` (pydantic, `from_attributes=True`) mirroring FeedItem columns.
  - `app.routers.feed.router` (`APIRouter(prefix="/api")`).
  - `GET /api/feed?sort_by=date|views|likes&content_type=&limit=` returning `list[FeedItemOut]`, published only, ordered: `date`→`created_at desc`, `views`→`views desc`, `likes`→`likes desc`. `limit` default 50, cap 200.

- [ ] **Step 1: Write the failing test `tests/test_feed_get.py`**

```python
from app.models import FeedItem
import app.db as db


def _make(session, **kw):
    defaults = dict(
        content_type="article", source_url="https://e.com/x",
        dedup_hash="h", source_type="manual",
        shared_by_name="A", shared_by_email="a@x.com",
    )
    defaults.update(kw)
    session.add(FeedItem(**defaults))


def test_feed_sorts_by_views(client):
    with db.SessionLocal() as s:
        _make(s, dedup_hash="a", views=1, title="low")
        _make(s, dedup_hash="b", views=9, title="high")
        s.commit()
    resp = client.get("/api/feed?sort_by=views")
    assert resp.status_code == 200
    titles = [r["title"] for r in resp.json()]
    assert titles == ["high", "low"]


def test_feed_excludes_draft(client):
    with db.SessionLocal() as s:
        _make(s, dedup_hash="d", status="draft", title="hidden")
        s.commit()
    resp = client.get("/api/feed")
    assert resp.status_code == 200
    assert resp.json() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_feed_get.py -v`
Expected: FAIL (route 404 / import error).

- [ ] **Step 3: Write `app/schemas.py`**

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FeedItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content_type: str
    source_url: str
    title: str | None
    author: str | None
    article_summary: str | None
    image_url: str | None
    source_type: str
    status: str
    shared_by_name: str
    shared_by_email: str
    views: int
    likes: int
    created_at: datetime


class FeedItemCreate(BaseModel):
    url: str
    title: str | None = None
    description: str | None = None
    shared_by_name: str = "Anonymous"
    shared_by_email: str = "anonymous@company.internal"
```

- [ ] **Step 4: Write `app/routers/feed.py`**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import FeedItem
from app.schemas import FeedItemOut

router = APIRouter(prefix="/api")

_SORT = {
    "date": FeedItem.created_at.desc(),
    "views": FeedItem.views.desc(),
    "likes": FeedItem.likes.desc(),
}


@router.get("/feed", response_model=list[FeedItemOut])
def get_feed(
    sort_by: str = "date",
    content_type: str | None = None,
    limit: int = Query(default=50, le=200),
    session: Session = Depends(get_session),
):
    order = _SORT.get(sort_by, _SORT["date"])
    stmt = select(FeedItem).where(FeedItem.status == "published")
    if content_type:
        stmt = stmt.where(FeedItem.content_type == content_type)
    stmt = stmt.order_by(order).limit(limit)
    return session.execute(stmt).scalars().all()
```

- [ ] **Step 5: Mount router — modify `app/main.py`**

Add after CORS middleware and before the health route, inside `create_app`:
```python
    from app.routers.feed import router as feed_router
    app.include_router(feed_router)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_feed_get.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/schemas.py app/routers app/main.py tests/test_feed_get.py
git commit -m "feat(be): add GET /api/feed with sorting"
```

---

### Task A5: view + like endpoints

**Files:**
- Modify: `app/routers/feed.py` (add two routes)
- Test: `tests/test_feed_engagement.py`

**Interfaces:**
- Consumes: `app.db.get_session`, `app.models.FeedItem`.
- Produces: `POST /api/feed/{id}/view` → `{ "views": int }` (404 if missing); `POST /api/feed/{id}/like` → `{ "likes": int }` (404 if missing).

- [ ] **Step 1: Write the failing test `tests/test_feed_engagement.py`**

```python
from app.models import FeedItem
import app.db as db


def _seed(dedup="e"):
    with db.SessionLocal() as s:
        item = FeedItem(
            content_type="article", source_url="https://e.com/x",
            dedup_hash=dedup, source_type="manual",
            shared_by_name="A", shared_by_email="a@x.com",
            views=0, likes=0,
        )
        s.add(item)
        s.commit()
        return item.id


def test_view_increments(client):
    fid = _seed("v")
    r1 = client.post(f"/api/feed/{fid}/view")
    r2 = client.post(f"/api/feed/{fid}/view")
    assert r1.json()["views"] == 1
    assert r2.json()["views"] == 2


def test_like_increments(client):
    fid = _seed("l")
    r = client.post(f"/api/feed/{fid}/like")
    assert r.json()["likes"] == 1


def test_view_missing_404(client):
    assert client.post("/api/feed/99999/view").status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_feed_engagement.py -v`
Expected: FAIL (404 on all / route missing).

- [ ] **Step 3: Add routes to `app/routers/feed.py`**

Add imports at top: `from fastapi import HTTPException`. Append:
```python
def _bump(session: Session, feed_id: int, column):
    item = session.get(FeedItem, feed_id)
    if item is None:
        raise HTTPException(status_code=404, detail="not found")
    setattr(item, column, getattr(item, column) + 1)
    session.commit()
    return getattr(item, column)


@router.post("/feed/{feed_id}/view")
def add_view(feed_id: int, session: Session = Depends(get_session)):
    return {"views": _bump(session, feed_id, "views")}


@router.post("/feed/{feed_id}/like")
def add_like(feed_id: int, session: Session = Depends(get_session)):
    return {"likes": _bump(session, feed_id, "likes")}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_feed_engagement.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routers/feed.py tests/test_feed_engagement.py
git commit -m "feat(be): add view/like increment endpoints"
```

---

### Task A6: OG scraper

**Files:**
- Create: `app/ingest/scraper.py`
- Test: `tests/test_scraper.py`

**Interfaces:**
- Consumes: nothing (pure parser + optional fetch).
- Produces:
  - `app.ingest.scraper.parse_metadata(html: str, url: str) -> dict` returning keys `title`, `image_url`, `summary` (from OG tags / `<title>` / meta description; missing → `None`).
  - `app.ingest.scraper.fetch_metadata(url: str, timeout: float = 8.0) -> dict` — httpx GET then `parse_metadata`; on any exception returns `{"title": None, "image_url": None, "summary": None}`.

- [ ] **Step 1: Write the failing test `tests/test_scraper.py`**

```python
from app.ingest.scraper import parse_metadata


def test_parse_og_tags():
    html = """
    <html><head>
      <meta property="og:title" content="Cool AI Thing">
      <meta property="og:image" content="https://img.example/x.png">
      <meta property="og:description" content="A short summary.">
    </head><body></body></html>
    """
    meta = parse_metadata(html, "https://example.com/a")
    assert meta["title"] == "Cool AI Thing"
    assert meta["image_url"] == "https://img.example/x.png"
    assert meta["summary"] == "A short summary."


def test_parse_falls_back_to_title_tag():
    html = "<html><head><title>Plain Title</title></head><body></body></html>"
    meta = parse_metadata(html, "https://example.com/a")
    assert meta["title"] == "Plain Title"
    assert meta["image_url"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scraper.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `app/ingest/scraper.py`**

```python
import httpx
from bs4 import BeautifulSoup


def _meta(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None


def parse_metadata(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = _meta(soup, "og:title")
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()
    summary = _meta(soup, "og:description") or _meta(soup, "description")
    image_url = _meta(soup, "og:image")
    return {"title": title, "image_url": image_url, "summary": summary}


def fetch_metadata(url: str, timeout: float = 8.0) -> dict:
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True,
                         headers={"user-agent": "reels-bot/1.0"})
        resp.raise_for_status()
        return parse_metadata(resp.text, url)
    except Exception:
        return {"title": None, "image_url": None, "summary": None}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scraper.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/ingest/scraper.py tests/test_scraper.py
git commit -m "feat(be): add OG metadata scraper"
```

---

### Task A7: Rate limiter + POST /api/feed (manual submit)

**Files:**
- Create: `app/ratelimit.py`
- Modify: `app/routers/feed.py` (add POST /feed)
- Test: `tests/test_feed_submit.py`

**Interfaces:**
- Consumes: `app.ingest.classify.classify_url`, `app.ingest.dedupe.dedup_hash`, `app.ingest.scraper.fetch_metadata`, `app.config.get_settings`.
- Produces:
  - `app.ratelimit.rate_limit(request: Request)` — FastAPI dependency; raises `HTTPException(429)` when a client IP exceeds `settings.rate_limit_max` per 60s window (in-memory).
  - `POST /api/feed` accepting `FeedItemCreate`; validates `url` starts with `http`, classifies content_type, scrapes OG for missing title/image/summary, inserts as `source_type='manual'`, `status='published'`. Returns `FeedItemOut` (201). Duplicate `dedup_hash` → 409.

- [ ] **Step 1: Write the failing test `tests/test_feed_submit.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_feed_submit.py -v`
Expected: FAIL (route missing).

- [ ] **Step 3: Write `app/ratelimit.py`**

```python
import time

from fastapi import HTTPException, Request

from app.config import get_settings

_hits: dict[str, list[float]] = {}
_WINDOW = 60.0


def rate_limit(request: Request) -> None:
    limit = get_settings().rate_limit_max
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    recent = [t for t in _hits.get(ip, []) if now - t < _WINDOW]
    if len(recent) >= limit:
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    recent.append(now)
    _hits[ip] = recent
```

- [ ] **Step 4: Add POST /feed to `app/routers/feed.py`**

Add imports at top:
```python
from fastapi import Request, status
from app.schemas import FeedItemCreate
from app.ingest.classify import classify_url
from app.ingest.dedupe import dedup_hash
from app.ingest.scraper import fetch_metadata
from app.ratelimit import rate_limit
```
Append route:
```python
@router.post("/feed", response_model=FeedItemOut, status_code=status.HTTP_201_CREATED)
def submit_feed(
    payload: FeedItemCreate,
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(rate_limit),
):
    url = payload.url.strip()
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="url must be http(s)")
    meta = fetch_metadata(url)
    title = payload.title or meta["title"] or url
    summary = payload.description or meta["summary"]
    h = dedup_hash(url, title)
    if session.query(FeedItem).filter_by(dedup_hash=h).first():
        raise HTTPException(status_code=409, detail="duplicate")
    item = FeedItem(
        content_type=classify_url(url),
        source_url=url,
        dedup_hash=h,
        title=title,
        article_summary=summary,
        image_url=meta["image_url"],
        source_type="manual",
        status="published",
        shared_by_name=payload.shared_by_name,
        shared_by_email=payload.shared_by_email,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_feed_submit.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/ratelimit.py app/routers/feed.py tests/test_feed_submit.py
git commit -m "feat(be): add rate-limited manual submit endpoint"
```

---

### Task A8: LLM provider abstraction (ollama default)

**Files:**
- Create: `app/llm/__init__.py` (empty)
- Create: `app/llm/prompts.py`
- Create: `app/llm/base.py`
- Create: `app/llm/ollama.py`
- Create: `app/llm/anthropic.py`
- Create: `app/llm/openai.py`
- Create: `app/llm/factory.py`
- Test: `tests/test_llm_factory.py`

**Interfaces:**
- Consumes: `app.config.get_settings`.
- Produces:
  - `app.llm.base.ModelProvider` — Protocol with `summarize(self, title: str, text: str) -> str`.
  - `app.llm.ollama.OllamaProvider`, `app.llm.anthropic.AnthropicProvider`, `app.llm.openai.OpenAIProvider` — each implements `summarize`.
  - `app.llm.factory.get_provider() -> ModelProvider` — chooses by `settings.model_provider`.
  - `app.llm.prompts.SUMMARIZE_SYSTEM: str`, `app.llm.prompts.summarize_user(title, text) -> str`.

- [ ] **Step 1: Write `app/llm/prompts.py`**

```python
SUMMARIZE_SYSTEM = (
    "You summarize AI/ML/Data-Science articles for an internal feed. "
    "Reply with 2-3 punchy sentences describing what the item is and why it "
    "matters. No preamble, no markdown."
)


def summarize_user(title: str, text: str) -> str:
    return f"Title: {title}\n\nContent:\n{text[:6000]}"
```

- [ ] **Step 2: Write `app/llm/base.py`**

```python
from typing import Protocol


class ModelProvider(Protocol):
    def summarize(self, title: str, text: str) -> str: ...
```

- [ ] **Step 3: Write `app/llm/ollama.py`**

```python
import httpx

from app.config import get_settings
from app.llm.prompts import SUMMARIZE_SYSTEM, summarize_user


class OllamaProvider:
    def summarize(self, title: str, text: str) -> str:
        s = get_settings()
        resp = httpx.post(
            f"{s.ollama_base_url}/api/chat",
            json={
                "model": s.ollama_model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": SUMMARIZE_SYSTEM},
                    {"role": "user", "content": summarize_user(title, text)},
                ],
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
```

- [ ] **Step 4: Write `app/llm/anthropic.py`**

```python
import httpx

from app.config import get_settings
from app.llm.prompts import SUMMARIZE_SYSTEM, summarize_user


class AnthropicProvider:
    def summarize(self, title: str, text: str) -> str:
        s = get_settings()
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": s.anthropic_api_key or "",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": s.anthropic_model,
                "max_tokens": 300,
                "system": SUMMARIZE_SYSTEM,
                "messages": [{"role": "user", "content": summarize_user(title, text)}],
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"].strip()
```

- [ ] **Step 5: Write `app/llm/openai.py`**

```python
import httpx

from app.config import get_settings
from app.llm.prompts import SUMMARIZE_SYSTEM, summarize_user


class OpenAIProvider:
    def summarize(self, title: str, text: str) -> str:
        s = get_settings()
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"authorization": f"Bearer {s.openai_api_key or ''}"},
            json={
                "model": s.openai_model,
                "messages": [
                    {"role": "system", "content": SUMMARIZE_SYSTEM},
                    {"role": "user", "content": summarize_user(title, text)},
                ],
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
```

- [ ] **Step 6: Write `app/llm/factory.py`**

```python
from app.config import get_settings
from app.llm.base import ModelProvider
from app.llm.anthropic import AnthropicProvider
from app.llm.ollama import OllamaProvider
from app.llm.openai import OpenAIProvider


def get_provider() -> ModelProvider:
    provider = get_settings().model_provider.lower()
    if provider == "anthropic":
        return AnthropicProvider()
    if provider == "openai":
        return OpenAIProvider()
    return OllamaProvider()
```

- [ ] **Step 7: Write the failing test `tests/test_llm_factory.py`**

```python
from app.llm.factory import get_provider
from app.llm.ollama import OllamaProvider
from app.config import get_settings


def test_factory_defaults_to_ollama():
    get_settings.cache_clear()
    assert isinstance(get_provider(), OllamaProvider)
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_llm_factory.py -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add app/llm tests/test_llm_factory.py
git commit -m "feat(be): add LLM provider abstraction with ollama default"
```

---

### Task A9: Sources config + RSS/HTML scanner

**Files:**
- Create: `sources.config.json`
- Create: `app/ingest/sources.py`
- Create: `app/ingest/rss_scanner.py`
- Test: `tests/test_rss_scanner.py`

**Interfaces:**
- Consumes: `app.db.SessionLocal`, `app.models.Source`, `app.models.FeedItem`, `app.ingest.scraper.fetch_metadata`, `app.ingest.dedupe.dedup_hash`, `app.llm.factory.get_provider`.
- Produces:
  - `app.ingest.sources.sync_sources() -> None` — upsert `sources.config.json` rows into `sources` table (match on `url`).
  - `app.ingest.rss_scanner.scan_source(session, source, provider) -> int` — parse RSS feed (feedparser), for each new entry insert a `FeedItem` (`content_type='article'`, `source_type='auto'`, `status='published'`, `shared_by_name='System Auto-Pull'`, `shared_by_email='system@company.internal'`), summarizing via `provider.summarize`; on provider error fall back to entry summary. Returns count inserted. Skips duplicates by `dedup_hash`.
  - `app.ingest.rss_scanner.run_scan() -> int` — loop active sources, sum inserts.

- [ ] **Step 1: Write `sources.config.json`**

```json
[
  { "kind": "rss", "name": "Hugging Face Blog", "url": "https://huggingface.co/blog/feed.xml" },
  { "kind": "rss", "name": "OpenAI News", "url": "https://openai.com/news/rss.xml" },
  { "kind": "rss", "name": "Google AI Blog", "url": "https://blog.google/technology/ai/rss/" }
]
```

- [ ] **Step 2: Write `app/ingest/sources.py`**

```python
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
```

- [ ] **Step 3: Write `app/ingest/rss_scanner.py`**

```python
import logging

import feedparser

from app.db import SessionLocal
from app.ingest.dedupe import dedup_hash
from app.ingest.scraper import fetch_metadata
from app.llm.factory import get_provider
from app.models import FeedItem, Source

log = logging.getLogger("rss_scanner")


def scan_source(session, source: Source, provider) -> int:
    feed = feedparser.parse(source.url)
    inserted = 0
    for entry in feed.entries[:10]:
        url = entry.get("link")
        title = entry.get("title") or url
        if not url:
            continue
        h = dedup_hash(url, title)
        if session.query(FeedItem).filter_by(dedup_hash=h).first():
            continue
        raw = entry.get("summary", "")
        try:
            summary = provider.summarize(title, raw)
        except Exception as exc:  # noqa: BLE001 — never crash a scan
            log.warning("summarize failed for %s: %s", url, exc)
            summary = raw[:500] or None
        image = fetch_metadata(url)["image_url"]
        session.add(FeedItem(
            content_type="article", source_url=url, dedup_hash=h,
            title=title, article_summary=summary, image_url=image,
            source_type="auto", status="published",
            shared_by_name="System Auto-Pull",
            shared_by_email="system@company.internal",
        ))
        inserted += 1
    session.commit()
    return inserted


def run_scan() -> int:
    provider = get_provider()
    total = 0
    with SessionLocal() as s:
        for source in s.query(Source).filter_by(is_active=True, kind="rss").all():
            try:
                total += scan_source(s, source, provider)
            except Exception as exc:  # noqa: BLE001
                log.warning("scan failed for %s: %s", source.url, exc)
    return total
```

- [ ] **Step 4: Write the failing test `tests/test_rss_scanner.py`**

```python
from unittest.mock import patch

import app.ingest.rss_scanner as scanner
from app.models import Source, FeedItem
import app.db as db


class FakeProvider:
    def summarize(self, title, text):
        return f"summary of {title}"


def test_scan_inserts_and_dedupes(session_factory, monkeypatch):
    monkeypatch.setattr(scanner, "fetch_metadata", lambda url: {"image_url": None})
    fake_feed = type("F", (), {"entries": [
        {"link": "https://e.com/1", "title": "One", "summary": "raw"},
        {"link": "https://e.com/1", "title": "One", "summary": "raw"},
    ]})()
    with patch.object(scanner, "feedparser") as fp:
        fp.parse.return_value = fake_feed
        with db.SessionLocal() as s:
            src = Source(kind="rss", name="X", url="https://feed")
            s.add(src); s.commit()
            n = scanner.scan_source(s, src, FakeProvider())
            assert n == 1
            items = s.query(FeedItem).all()
            assert len(items) == 1
            assert items[0].article_summary == "summary of One"
            assert items[0].source_type == "auto"
            assert items[0].shared_by_name == "System Auto-Pull"


def test_scan_falls_back_on_provider_error(session_factory, monkeypatch):
    monkeypatch.setattr(scanner, "fetch_metadata", lambda url: {"image_url": None})
    fake_feed = type("F", (), {"entries": [
        {"link": "https://e.com/2", "title": "Two", "summary": "raw text"},
    ]})()

    class Boom:
        def summarize(self, title, text):
            raise RuntimeError("model down")

    with patch.object(scanner, "feedparser") as fp:
        fp.parse.return_value = fake_feed
        with db.SessionLocal() as s:
            src = Source(kind="rss", name="Y", url="https://feed2")
            s.add(src); s.commit()
            scanner.scan_source(s, src, Boom())
            item = s.query(FeedItem).first()
            assert item.article_summary == "raw text"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_rss_scanner.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sources.config.json app/ingest/sources.py app/ingest/rss_scanner.py tests/test_rss_scanner.py
git commit -m "feat(be): add sources config, RSS scanner with LLM summarize + fallback"
```

---

### Task A10: X.com sync

**Files:**
- Create: `app/ingest/x_sync.py`
- Test: `tests/test_x_sync.py`

**Interfaces:**
- Consumes: `app.db.SessionLocal`, `app.models.MonitoredXAccount`, `app.models.FeedItem`, `app.ingest.dedupe.dedup_hash`, `app.config.get_settings`.
- Produces:
  - `app.ingest.x_sync.fetch_tweets(x_user_id, since_id, bearer) -> list[dict]` — httpx GET `https://api.twitter.com/2/users/{id}/tweets?max_results=10[&since_id=]`; returns `data` list (empty on error).
  - `app.ingest.x_sync.sync_account(session, account, bearer) -> int` — insert new tweets as `FeedItem` (`content_type='x'`, `source_url=https://x.com/i/web/status/{id}`, `source_type='auto'`, `status='published'`, `shared_by_name='System Auto-Pull'`), update `account.last_tweet_id` to newest. Returns inserted count.
  - `app.ingest.x_sync.run_x_sync() -> int` — loop active accounts; no-op returning 0 if `x_bearer_token` unset.

- [ ] **Step 1: Write the failing test `tests/test_x_sync.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_x_sync.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `app/ingest/x_sync.py`**

```python
import logging

import httpx

from app.config import get_settings
from app.db import SessionLocal
from app.ingest.dedupe import dedup_hash
from app.models import FeedItem, MonitoredXAccount

log = logging.getLogger("x_sync")


def fetch_tweets(x_user_id: str, since_id: str | None, bearer: str) -> list[dict]:
    params = {"max_results": 10}
    if since_id:
        params["since_id"] = since_id
    try:
        resp = httpx.get(
            f"https://api.twitter.com/2/users/{x_user_id}/tweets",
            params=params,
            headers={"authorization": f"Bearer {bearer}"},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception as exc:  # noqa: BLE001
        log.warning("x fetch failed for %s: %s", x_user_id, exc)
        return []


def sync_account(session, account: MonitoredXAccount, bearer: str) -> int:
    tweets = fetch_tweets(account.x_user_id, account.last_tweet_id, bearer)
    inserted = 0
    newest = account.last_tweet_id
    for tw in tweets:
        tid = tw["id"]
        url = f"https://x.com/i/web/status/{tid}"
        h = dedup_hash(url, tid)
        if session.query(FeedItem).filter_by(dedup_hash=h).first():
            continue
        session.add(FeedItem(
            content_type="x", source_url=url, dedup_hash=h,
            title=tw.get("text", "")[:280], article_summary=tw.get("text"),
            source_type="auto", status="published",
            shared_by_name="System Auto-Pull",
            shared_by_email="system@company.internal",
        ))
        inserted += 1
        if newest is None or int(tid) > int(newest):
            newest = tid
    account.last_tweet_id = newest
    session.commit()
    return inserted


def run_x_sync() -> int:
    bearer = get_settings().x_bearer_token
    if not bearer:
        return 0
    total = 0
    with SessionLocal() as s:
        for acct in s.query(MonitoredXAccount).filter_by(is_active=True).all():
            total += sync_account(s, acct, bearer)
    return total
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_x_sync.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/ingest/x_sync.py tests/test_x_sync.py
git commit -m "feat(be): add X.com scheduled sync with since_id pagination"
```

---

### Task A11: Scheduler + lifespan wiring + manual scan route

**Files:**
- Create: `app/scheduler.py`
- Modify: `app/main.py` (lifespan: migrate → sync_sources → start scheduler)
- Modify: `app/routers/feed.py` (add `POST /api/scan`)
- Test: `tests/test_scan_route.py`

**Interfaces:**
- Consumes: `app.ingest.rss_scanner.run_scan`, `app.ingest.x_sync.run_x_sync`, `app.ingest.sources.sync_sources`, `app.db.migrate`, `app.config.get_settings`.
- Produces:
  - `app.scheduler.start_scheduler() -> BackgroundScheduler | None` — if `scan_enabled`, schedules `run_scan` on `scan_cron` and `run_x_sync` every `x_sync_interval_hours`. Returns scheduler (or None when disabled).
  - `POST /api/scan` → `{ "ok": true }` (202), triggers `run_scan` in a thread.

- [ ] **Step 1: Write `app/scheduler.py`**

```python
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.ingest.rss_scanner import run_scan
from app.ingest.x_sync import run_x_sync

log = logging.getLogger("scheduler")


def start_scheduler() -> BackgroundScheduler | None:
    s = get_settings()
    if not s.scan_enabled:
        log.info("scheduler disabled (SCAN_ENABLED=false)")
        return None
    sched = BackgroundScheduler()
    sched.add_job(run_scan, CronTrigger.from_crontab(s.scan_cron), id="rss_scan")
    sched.add_job(run_x_sync, "interval", hours=s.x_sync_interval_hours, id="x_sync")
    sched.start()
    log.info("scheduler started")
    return sched
```

- [ ] **Step 2: Rewrite `app/main.py` with lifespan**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db import migrate
    from app.ingest.sources import sync_sources
    from app.scheduler import start_scheduler

    migrate()
    sync_sources()
    sched = start_scheduler()
    try:
        yield
    finally:
        if sched is not None:
            sched.shutdown(wait=False)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="reels-be", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.routers.feed import router as feed_router
    app.include_router(feed_router)

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    return app


app = create_app()
```

Note: `TestClient(create_app())` runs the lifespan (migrate) on startup. Tests using `session_factory` override `SessionLocal` after the app is created; the fixture order (session_factory before client) keeps this correct. To avoid `migrate()` hitting the default sqlite file during tests, add the guard below.

- [ ] **Step 3: Guard migrate() so tests don't touch the default DB**

In `tests/conftest.py`, before creating the client, monkeypatch `migrate` to a no-op. Update the `client` fixture:
```python
@pytest.fixture
def client(session_factory, monkeypatch):
    import app.db as _db
    monkeypatch.setattr(_db, "migrate", lambda: None)
    monkeypatch.setattr("app.scheduler.start_scheduler", lambda: None)
    from app.main import create_app
    return TestClient(create_app())
```

- [ ] **Step 4: Add `POST /api/scan` to `app/routers/feed.py`**

Add import: `import threading` and `from app.ingest.rss_scanner import run_scan`. Append:
```python
@router.post("/scan", status_code=202)
def trigger_scan():
    threading.Thread(target=run_scan, daemon=True).start()
    return {"ok": True}
```

- [ ] **Step 5: Write the failing test `tests/test_scan_route.py`**

```python
import app.routers.feed as feed_mod


def test_scan_route_triggers(client, monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(feed_mod, "run_scan", lambda: called.__setitem__("n", 1))
    resp = client.post("/api/scan")
    assert resp.status_code == 202
    assert resp.json() == {"ok": True}
```

- [ ] **Step 6: Run the full suite**

Run: `pytest -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add app/scheduler.py app/main.py app/routers/feed.py tests/conftest.py tests/test_scan_route.py
git commit -m "feat(be): wire APScheduler in lifespan + manual scan route"
```

---

### Task A12: Backend Dockerfile

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

**Interfaces:**
- Consumes: `pyproject.toml`, `app/`.
- Produces: an image running `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

- [ ] **Step 1: Write `Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .
COPY app ./app
COPY sources.config.json ./
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Write `.dockerignore`**

```
.venv/
__pycache__/
*.db
tests/
.env
```

- [ ] **Step 3: Build to verify**

Run: `docker build -t reels-be .`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "chore(be): add Dockerfile"
```

---

## Phase B — Frontend (reels-fe)

Run all Phase B commands from `/Users/levy/Code/reels/reels-fe`.

### Task B1: Restructure repo to client-only + configurable API base

**Files:**
- Delete: `reels-fe/server/` (entire dir)
- Delete: `reels-fe/tsconfig.json`, `reels-fe/sources.config.json` (server-era root files)
- Move: `client/*` → repo root (so `src/`, `index.html`, `vite.config.ts`, `package.json`, etc. sit at `reels-fe/` root)
- Modify: root `package.json` (drop server scripts/deps; keep the client's)
- Create: `.env.example`

**Interfaces:**
- Consumes: nothing.
- Produces: a Vite React project rooted at `reels-fe/` with `npm run dev` serving the client; `VITE_API_BASE_URL` env consumed by `api.ts` (Task B2).

- [ ] **Step 1: Move client to root and remove the server**

```bash
git rm -r server
git rm tsconfig.json sources.config.json
git mv client/index.html client/package.json client/package-lock.json client/tsconfig.json client/vite.config.ts ./
git mv client/src ./src
git mv client/public ./public
rmdir client
```

- [ ] **Step 2: Rewrite root `package.json`**

```json
{
  "name": "reels-fe",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "icons": "node scripts/generate-icons.mjs"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.18",
    "@types/react-dom": "^18.3.5",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.7.2",
    "vite": "^6.0.7",
    "vitest": "^2.1.8"
  }
}
```

- [ ] **Step 3: Set the dev proxy + env in `vite.config.ts`**

Replace `vite.config.ts` with:
```ts
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_API_BASE_URL || "http://localhost:8000";
  return {
    plugins: [react()],
    server: { proxy: { "/api": target } },
  };
});
```

- [ ] **Step 4: Write `.env.example`**

```
# Backend base URL. Empty in dev uses the Vite proxy to localhost:8000.
VITE_API_BASE_URL=
```

- [ ] **Step 5: Install and verify dev server boots**

Run:
```bash
npm install
npm run build
```
Expected: build succeeds (existing components still compile; they are replaced in later tasks).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(fe): flatten to client-only repo, remove server, add API base config"
```

---

### Task B2: API client (types + fetch functions)

**Files:**
- Modify: `src/api.ts` (full rewrite)
- Create: `src/api.test.ts`

**Interfaces:**
- Consumes: `import.meta.env.VITE_API_BASE_URL`.
- Produces:
  - `FeedItem` type: `{ id, content_type: "youtube"|"x"|"reddit"|"article", source_url, title, author, article_summary, image_url, source_type: "auto"|"manual", status, shared_by_name, shared_by_email, views, likes, created_at }`.
  - `SortBy = "date" | "views" | "likes"`.
  - `fetchFeed(sortBy: SortBy): Promise<FeedItem[]>`.
  - `addView(id: number): Promise<void>`, `addLike(id: number): Promise<number>`.
  - `submitPost(body): Promise<void>`.
  - `apiUrl(path: string): string`.

- [ ] **Step 1: Write `src/api.ts`**

```ts
export type ContentType = "youtube" | "x" | "reddit" | "article";
export type SortBy = "date" | "views" | "likes";

export interface FeedItem {
  id: number;
  content_type: ContentType;
  source_url: string;
  title: string | null;
  author: string | null;
  article_summary: string | null;
  image_url: string | null;
  source_type: "auto" | "manual";
  status: string;
  shared_by_name: string;
  shared_by_email: string;
  views: number;
  likes: number;
  created_at: string;
}

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

export function apiUrl(path: string): string {
  return `${BASE}${path}`;
}

export async function fetchFeed(sortBy: SortBy): Promise<FeedItem[]> {
  const res = await fetch(apiUrl(`/api/feed?sort_by=${sortBy}`));
  if (!res.ok) throw new Error(`Failed to load feed (${res.status})`);
  return res.json();
}

export async function addView(id: number): Promise<void> {
  await fetch(apiUrl(`/api/feed/${id}/view`), { method: "POST" });
}

export async function addLike(id: number): Promise<number> {
  const res = await fetch(apiUrl(`/api/feed/${id}/like`), { method: "POST" });
  if (!res.ok) throw new Error(`Like failed (${res.status})`);
  return (await res.json()).likes as number;
}

export async function submitPost(body: {
  url: string;
  title?: string;
  description?: string;
  shared_by_name?: string;
  shared_by_email?: string;
}): Promise<void> {
  const res = await fetch(apiUrl("/api/feed"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(data?.detail ?? `Submission failed (${res.status})`);
  }
}

export function relativeTime(iso: string): string {
  const seconds = Math.max(1, Math.floor((Date.now() - Date.parse(iso)) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
```

- [ ] **Step 2: Write the failing test `src/api.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import { apiUrl, relativeTime } from "./api";

describe("api helpers", () => {
  it("apiUrl prefixes base (empty by default)", () => {
    expect(apiUrl("/api/feed")).toBe("/api/feed");
  });
  it("relativeTime returns seconds for recent", () => {
    expect(relativeTime(new Date().toISOString())).toMatch(/s$/);
  });
});
```

- [ ] **Step 3: Run test to verify it passes**

Run: `npm run test`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/api.ts src/api.test.ts
git commit -m "feat(fe): rewrite API client for feed_items + configurable base URL"
```

---

### Task B3: Content-type embed components

**Files:**
- Create: `src/components/YouTubeEmbed.tsx`
- Create: `src/components/XEmbed.tsx`
- Create: `src/components/RedditEmbed.tsx`
- Create: `src/components/ArticleCard.tsx`
- Delete: `src/components/PostCard.tsx`

**Interfaces:**
- Consumes: `FeedItem` from `../api`.
- Produces (each `default`-less named export, props `{ item: FeedItem }`):
  - `YouTubeEmbed` — renders an iframe from the video id parsed out of `source_url`.
  - `XEmbed` — renders the tweet via `blockquote.twitter-tweet` linking `source_url` (no external script dependency required to compile).
  - `RedditEmbed` — renders a linked card to the Reddit post.
  - `ArticleCard` — dimmed full-bleed `image_url` + `title` + `article_summary` + "Read more ↗".
  - `youTubeId(url: string): string | null` exported from `YouTubeEmbed.tsx`.

- [ ] **Step 1: Write `src/components/YouTubeEmbed.tsx`**

```tsx
import type { FeedItem } from "../api";

export function youTubeId(url: string): string | null {
  try {
    const u = new URL(url);
    if (u.hostname.includes("youtu.be")) return u.pathname.slice(1) || null;
    return u.searchParams.get("v");
  } catch {
    return null;
  }
}

export function YouTubeEmbed({ item }: { item: FeedItem }) {
  const id = youTubeId(item.source_url);
  if (!id) return <ArticleFallback item={item} />;
  return (
    <div className="embed youtube">
      <iframe
        src={`https://www.youtube.com/embed/${id}?playsinline=1`}
        title={item.title ?? "YouTube video"}
        allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
      />
    </div>
  );
}

function ArticleFallback({ item }: { item: FeedItem }) {
  return (
    <div className="embed article-fallback">
      <a href={item.source_url} target="_blank" rel="noreferrer">
        {item.title ?? item.source_url} ↗
      </a>
    </div>
  );
}
```

- [ ] **Step 2: Write `src/components/XEmbed.tsx`**

```tsx
import type { FeedItem } from "../api";

export function XEmbed({ item }: { item: FeedItem }) {
  return (
    <div className="embed x">
      <blockquote className="twitter-tweet">
        <p>{item.article_summary ?? item.title}</p>
        <a href={item.source_url} target="_blank" rel="noreferrer">
          View on X ↗
        </a>
      </blockquote>
    </div>
  );
}
```

- [ ] **Step 3: Write `src/components/RedditEmbed.tsx`**

```tsx
import type { FeedItem } from "../api";

export function RedditEmbed({ item }: { item: FeedItem }) {
  return (
    <div className="embed reddit">
      <a className="reddit-card" href={item.source_url} target="_blank" rel="noreferrer">
        <span className="reddit-tag">reddit</span>
        <h2>{item.title ?? "Reddit post"}</h2>
        {item.article_summary && <p>{item.article_summary}</p>}
      </a>
    </div>
  );
}
```

- [ ] **Step 4: Write `src/components/ArticleCard.tsx`**

```tsx
import type { FeedItem } from "../api";

export function ArticleCard({ item }: { item: FeedItem }) {
  return (
    <div
      className="embed article"
      style={item.image_url ? { backgroundImage: `url(${item.image_url})` } : undefined}
    >
      <div className="article-scrim">
        <h2>{item.title ?? "Untitled"}</h2>
        {item.article_summary && <p>{item.article_summary}</p>}
        <a className="read-more" href={item.source_url} target="_blank" rel="noreferrer">
          Read more ↗
        </a>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Remove the old card**

```bash
git rm src/components/PostCard.tsx
```

- [ ] **Step 6: Commit**

```bash
git add src/components/YouTubeEmbed.tsx src/components/XEmbed.tsx src/components/RedditEmbed.tsx src/components/ArticleCard.tsx
git commit -m "feat(fe): add per-content-type embed components"
```

---

### Task B4: Slide dispatcher (with vitest)

**Files:**
- Create: `src/components/Slide.tsx`
- Create: `src/components/Slide.test.tsx`
- Create: `vitest.config.ts`

**Interfaces:**
- Consumes: the four embed components, `AttributionBadge` (Task B5 — but Slide must compile now, so import is added in B5; for B4 Slide renders embed + a placeholder footer).
- Produces: `Slide({ item, onLike }: { item: FeedItem; onLike: (id: number) => void })` choosing the renderer by `item.content_type`. Exported helper `pickRenderer(type: ContentType)` returns the component function for unit testing.

- [ ] **Step 1: Write `vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", globals: true },
});
```

- [ ] **Step 2: Add jsdom + testing-library to devDeps**

Run:
```bash
npm install -D jsdom @testing-library/react @testing-library/jest-dom
```

- [ ] **Step 3: Write `src/components/Slide.tsx`**

```tsx
import type { ContentType, FeedItem } from "../api";
import { YouTubeEmbed } from "./YouTubeEmbed";
import { XEmbed } from "./XEmbed";
import { RedditEmbed } from "./RedditEmbed";
import { ArticleCard } from "./ArticleCard";

export function pickRenderer(type: ContentType) {
  switch (type) {
    case "youtube":
      return YouTubeEmbed;
    case "x":
      return XEmbed;
    case "reddit":
      return RedditEmbed;
    default:
      return ArticleCard;
  }
}

export function Slide({ item }: { item: FeedItem; onLike?: (id: number) => void }) {
  const Renderer = pickRenderer(item.content_type);
  return (
    <section className="slide" data-id={item.id}>
      <Renderer item={item} />
    </section>
  );
}
```

- [ ] **Step 4: Write the failing test `src/components/Slide.test.tsx`**

```tsx
import { describe, it, expect } from "vitest";
import { pickRenderer } from "./Slide";
import { YouTubeEmbed } from "./YouTubeEmbed";
import { ArticleCard } from "./ArticleCard";
import { RedditEmbed } from "./RedditEmbed";

describe("pickRenderer", () => {
  it("maps content types to components", () => {
    expect(pickRenderer("youtube")).toBe(YouTubeEmbed);
    expect(pickRenderer("reddit")).toBe(RedditEmbed);
    expect(pickRenderer("article")).toBe(ArticleCard);
  });
});
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm run test`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/components/Slide.tsx src/components/Slide.test.tsx vitest.config.ts package.json package-lock.json
git commit -m "feat(fe): add content-type slide dispatcher with tests"
```

---

### Task B5: AttributionBadge + like overlay

**Files:**
- Create: `src/components/AttributionBadge.tsx`
- Create: `src/components/Overlay.tsx`
- Modify: `src/components/Slide.tsx` (render Overlay over the embed)
- Create: `src/components/AttributionBadge.test.tsx`

**Interfaces:**
- Consumes: `FeedItem`, `addLike` from `../api`.
- Produces:
  - `AttributionBadge({ item })` — if `item.shared_by_name === "System Auto-Pull"` renders `.badge.auto` with a 🤖 and "Verified Source"; else `.badge.manual` with "Shared by {name}". Exported `isAuto(item): boolean`.
  - `Overlay({ item })` — heart button showing `likes`, calls `addLike`, plus `<AttributionBadge>`.

- [ ] **Step 1: Write `src/components/AttributionBadge.tsx`**

```tsx
import type { FeedItem } from "../api";

export function isAuto(item: FeedItem): boolean {
  return item.shared_by_name === "System Auto-Pull";
}

export function AttributionBadge({ item }: { item: FeedItem }) {
  if (isAuto(item)) {
    return (
      <span className="badge auto">
        <span className="badge-icon">🤖</span> Verified Source
      </span>
    );
  }
  return (
    <span className="badge manual">
      <span className="badge-icon">👤</span> Shared by {item.shared_by_name}
    </span>
  );
}
```

- [ ] **Step 2: Write `src/components/Overlay.tsx`**

```tsx
import { useState } from "react";
import type { FeedItem } from "../api";
import { addLike } from "../api";
import { AttributionBadge } from "./AttributionBadge";

export function Overlay({ item }: { item: FeedItem }) {
  const [likes, setLikes] = useState(item.likes);
  const [liked, setLiked] = useState(false);

  async function toggleLike() {
    if (liked) return;
    setLiked(true);
    try {
      setLikes(await addLike(item.id));
    } catch {
      setLiked(false);
    }
  }

  return (
    <div className="overlay">
      <AttributionBadge item={item} />
      <div className="overlay-actions">
        <button
          className={`like ${liked ? "liked" : ""}`}
          onClick={toggleLike}
          aria-label="like"
        >
          ♥ <span className="like-count">{likes}</span>
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Render Overlay in `src/components/Slide.tsx`**

Replace the `Slide` function body:
```tsx
export function Slide({ item }: { item: FeedItem; onLike?: (id: number) => void }) {
  const Renderer = pickRenderer(item.content_type);
  return (
    <section className="slide" data-id={item.id}>
      <Renderer item={item} />
      <Overlay item={item} />
    </section>
  );
}
```
Add import at top: `import { Overlay } from "./Overlay";`

- [ ] **Step 4: Write the failing test `src/components/AttributionBadge.test.tsx`**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AttributionBadge, isAuto } from "./AttributionBadge";
import type { FeedItem } from "../api";

const base: FeedItem = {
  id: 1, content_type: "article", source_url: "https://e.com", title: "t",
  author: null, article_summary: null, image_url: null, source_type: "auto",
  status: "published", shared_by_name: "System Auto-Pull",
  shared_by_email: "system@company.internal", views: 0, likes: 0,
  created_at: new Date().toISOString(),
};

describe("AttributionBadge", () => {
  it("flags auto content", () => {
    expect(isAuto(base)).toBe(true);
    render(<AttributionBadge item={base} />);
    expect(screen.getByText(/Verified Source/)).toBeTruthy();
  });
  it("shows sharer name for manual", () => {
    render(<AttributionBadge item={{ ...base, shared_by_name: "Alice" }} />);
    expect(screen.getByText(/Shared by Alice/)).toBeTruthy();
  });
});
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm run test`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/components/AttributionBadge.tsx src/components/Overlay.tsx src/components/Slide.tsx src/components/AttributionBadge.test.tsx
git commit -m "feat(fe): add attribution badge and like overlay"
```

---

### Task B6: ReelsFeed (scroll-snap + IntersectionObserver views)

**Files:**
- Create: `src/components/ReelsFeed.tsx`
- Delete: `src/components/Feed.tsx`

**Interfaces:**
- Consumes: `fetchFeed`, `addView`, `SortBy`, `FeedItem` from `../api`; `Slide`.
- Produces: `ReelsFeed({ sortBy }: { sortBy: SortBy })` — loads feed, renders one `Slide` per item in a scroll-snap container, uses `IntersectionObserver` (threshold 0.6) to fire `addView(id)` once per item when it becomes fully visible.

- [ ] **Step 1: Write `src/components/ReelsFeed.tsx`**

```tsx
import { useEffect, useRef, useState } from "react";
import type { FeedItem, SortBy } from "../api";
import { fetchFeed, addView } from "../api";
import { Slide } from "./Slide";

export function ReelsFeed({ sortBy }: { sortBy: SortBy }) {
  const [items, setItems] = useState<FeedItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const seen = useRef<Set<number>>(new Set());
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchFeed(sortBy).then(setItems).catch((e: Error) => setError(e.message));
  }, [sortBy]);

  useEffect(() => {
    if (!items || !containerRef.current) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const id = Number((entry.target as HTMLElement).dataset.id);
          if (id && !seen.current.has(id)) {
            seen.current.add(id);
            addView(id).catch(() => {});
          }
        }
      },
      { threshold: 0.6 },
    );
    containerRef.current.querySelectorAll(".slide").forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [items]);

  if (error) return <div className="empty">couldn't load feed — {error}</div>;
  if (items === null) return <div className="empty">loading…</div>;
  if (items.length === 0) return <div className="empty">no posts yet</div>;

  return (
    <div className="reels" ref={containerRef}>
      {items.map((item) => (
        <Slide key={item.id} item={item} />
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Remove old Feed**

```bash
git rm src/components/Feed.tsx
```

- [ ] **Step 3: Commit**

```bash
git add src/components/ReelsFeed.tsx
git commit -m "feat(fe): add scroll-snap reels feed with view tracking"
```

---

### Task B7: SortControl + App shell + SubmitForm + styles

**Files:**
- Create: `src/components/SortControl.tsx`
- Modify: `src/components/SubmitForm.tsx` (point at new submitPost signature)
- Modify: `src/App.tsx` (reels shell with sort + submit route; drop review route)
- Delete: `src/components/Review.tsx`
- Modify: `src/styles.css` (append scroll-snap + slide + overlay + badge styles)

**Interfaces:**
- Consumes: `ReelsFeed`, `SortControl`, `SubmitForm`, `SortBy`.
- Produces:
  - `SortControl({ value, onChange }: { value: SortBy; onChange: (s: SortBy) => void })`.
  - `App` default export: hash routes `#/` (feed + sort) and `#/submit`.

- [ ] **Step 1: Write `src/components/SortControl.tsx`**

```tsx
import type { SortBy } from "../api";

const OPTIONS: { key: SortBy; label: string }[] = [
  { key: "date", label: "newest" },
  { key: "views", label: "most viewed" },
  { key: "likes", label: "most liked" },
];

export function SortControl({
  value,
  onChange,
}: {
  value: SortBy;
  onChange: (s: SortBy) => void;
}) {
  return (
    <div className="sort-control">
      {OPTIONS.map((o) => (
        <button
          key={o.key}
          className={value === o.key ? "active" : ""}
          onClick={() => onChange(o.key)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Rewrite `src/components/SubmitForm.tsx`**

```tsx
import { useState } from "react";
import { submitPost } from "../api";

export function SubmitForm() {
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("submitting…");
    try {
      await submitPost({ url, shared_by_name: name || "Anonymous" });
      setStatus("✅ added to the feed");
      setUrl("");
    } catch (err) {
      setStatus(`❌ ${(err as Error).message}`);
    }
  }

  return (
    <form className="submit-form" onSubmit={onSubmit}>
      <label>
        Link
        <input
          type="url"
          required
          placeholder="https://…"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
      </label>
      <label>
        Your name
        <input
          type="text"
          placeholder="optional"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      <button type="submit">submit</button>
      {status && <p className="submit-status">{status}</p>}
    </form>
  );
}
```

- [ ] **Step 3: Rewrite `src/App.tsx`**

```tsx
import { useEffect, useState } from "react";
import type { SortBy } from "./api";
import { ReelsFeed } from "./components/ReelsFeed";
import { SortControl } from "./components/SortControl";
import { SubmitForm } from "./components/SubmitForm";

type Route = "feed" | "submit";

function currentRoute(): Route {
  return window.location.hash === "#/submit" ? "submit" : "feed";
}

export default function App() {
  const [route, setRoute] = useState<Route>(currentRoute);
  const [sortBy, setSortBy] = useState<SortBy>("date");

  useEffect(() => {
    const onHash = () => setRoute(currentRoute());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  return (
    <>
      <header className="header">
        <h1>ReelAkamai<span className="cursor">_</span></h1>
        {route === "feed" && <SortControl value={sortBy} onChange={setSortBy} />}
      </header>

      {route === "feed" ? <ReelsFeed sortBy={sortBy} /> : <SubmitForm />}

      <nav className="nav">
        <a href="#/" className={route === "feed" ? "active" : ""}>feed</a>
        <a href="#/submit" className={route === "submit" ? "active" : ""}>+ submit</a>
      </nav>
    </>
  );
}
```

- [ ] **Step 4: Remove Review page**

```bash
git rm src/components/Review.tsx
```

- [ ] **Step 5: Append reels styles to `src/styles.css`**

```css
/* ---- Reels scroll-snap ---- */
.reels {
  height: 100dvh;
  overflow-y: scroll;
  scroll-snap-type: y mandatory;
  scroll-behavior: smooth;
}
.slide {
  position: relative;
  height: 100dvh;
  scroll-snap-align: start;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.embed { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }
.embed.youtube iframe, .embed.x { width: 100%; height: 100%; border: 0; }
.embed.article {
  background-size: cover;
  background-position: center;
  width: 100%;
  height: 100%;
}
.article-scrim {
  width: 100%; height: 100%;
  display: flex; flex-direction: column; justify-content: flex-end;
  gap: 12px; padding: 24px;
  background: linear-gradient(to top, rgba(0,0,0,0.85), rgba(0,0,0,0.1));
}
.article-scrim h2 { font-family: var(--font-display); font-size: 26px; }
.read-more { color: var(--auto); font-weight: 600; }
.reddit-card { display: block; padding: 24px; text-decoration: none; color: var(--text); }
.reddit-tag { color: #ff4500; font-weight: 700; }

/* ---- Overlay ---- */
.overlay {
  position: absolute; left: 0; right: 0; bottom: 0;
  display: flex; align-items: flex-end; justify-content: space-between;
  padding: 20px; pointer-events: none;
}
.overlay .badge, .overlay .like { pointer-events: auto; }
.badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 12px; border-radius: 999px; font-size: 13px;
  background: rgba(0,0,0,0.55); backdrop-filter: blur(6px);
}
.badge.auto {
  border: 1px solid transparent;
  background:
    linear-gradient(rgba(0,0,0,0.6), rgba(0,0,0,0.6)) padding-box,
    linear-gradient(90deg, var(--auto), #7c9dff) border-box;
}
.like { background: none; border: 0; color: var(--text); font-size: 28px; cursor: pointer; }
.like.liked { color: #ff3b5c; }
.like-count { font-size: 14px; }

/* ---- Sort control ---- */
.sort-control { display: flex; gap: 6px; }
.sort-control button {
  background: none; border: 0; color: var(--muted);
  font-size: 13px; cursor: pointer; padding: 4px 6px;
}
.sort-control button.active { color: var(--auto); }

/* ---- Submit form ---- */
.submit-form { display: flex; flex-direction: column; gap: 16px; padding: 24px; }
.submit-form label { display: flex; flex-direction: column; gap: 6px; }
.submit-form input {
  background: var(--surface); border: 1px solid #1c2230; color: var(--text);
  padding: 10px; border-radius: 8px;
}
```

- [ ] **Step 6: Verify build + tests**

Run: `npm run build && npm run test`
Expected: build succeeds, all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(fe): reels shell with sort control, submit form, reels styles"
```

---

### Task B8: Frontend Dockerfile

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

**Interfaces:**
- Consumes: the built `dist/`.
- Produces: an image serving the built PWA on port 5173 via `vite preview`.

- [ ] **Step 1: Write `Dockerfile`**

```dockerfile
FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-slim
WORKDIR /app
COPY --from=build /app/dist ./dist
COPY --from=build /app/package.json ./
RUN npm install -g serve
EXPOSE 5173
CMD ["serve", "-s", "dist", "-l", "5173"]
```

- [ ] **Step 2: Write `.dockerignore`**

```
node_modules/
dist/
.env
```

- [ ] **Step 3: Build to verify**

Run: `docker build -t reels-fe .`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "chore(fe): add Dockerfile serving built PWA"
```

---

## Phase C — Orchestration

### Task C1: docker-compose (postgres + backend + frontend, Ollama on host)

**Files:**
- Create: `reels-be/docker-compose.yml`
- Modify: `reels-be/README.md` (create if absent — add run instructions)

**Interfaces:**
- Consumes: `reels-be/Dockerfile`, `reels-fe/Dockerfile` (via `../reels-fe` build context).
- Produces: `docker compose up` running postgres + backend (:8000) + frontend (:5173), backend reaching host Ollama at `host.docker.internal:11434`.

- [ ] **Step 1: Write `reels-be/docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: reels
      POSTGRES_PASSWORD: reels
      POSTGRES_DB: reels
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U reels"]
      interval: 5s
      timeout: 3s
      retries: 10

  backend:
    build: .
    environment:
      DATABASE_URL: postgresql+psycopg2://reels:reels@db:5432/reels
      MODEL_PROVIDER: ollama
      OLLAMA_BASE_URL: http://host.docker.internal:11434
      OLLAMA_MODEL: gemma2:2b
      CORS_ORIGINS: http://localhost:5173
      SCAN_ENABLED: "true"
    extra_hosts: ["host.docker.internal:host-gateway"]
    depends_on:
      db:
        condition: service_healthy
    ports: ["8000:8000"]

  frontend:
    build: ../reels-fe
    environment:
      VITE_API_BASE_URL: http://localhost:8000
    depends_on: [backend]
    ports: ["5173:5173"]

volumes:
  pgdata:
```

- [ ] **Step 2: Write/append `reels-be/README.md`**

```markdown
# reels-be

Python/FastAPI backend for the internal AI reels feed. Pairs with `reels-fe`.

## Local dev (docker-compose)

Requires Docker and a host Ollama with the model pulled:

```sh
ollama pull gemma2:2b     # run once; keep `ollama serve` running
docker compose up --build
```

- Backend: http://localhost:8000 (health: `/api/health`)
- Frontend: http://localhost:5173
- Postgres: localhost:5432 (reels/reels)

The backend reaches the host's Ollama at `host.docker.internal:11434`.
Trigger a scan without waiting for cron: `curl -X POST localhost:8000/api/scan`.

## Backend without Docker

```sh
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg2://reels:reels@localhost:5432/reels
uvicorn app.main:app --reload --port 8000
pytest -v
```

## Switching LLM provider

Set `MODEL_PROVIDER=anthropic` (+ `ANTHROPIC_API_KEY`) or `openai` (+ `OPENAI_API_KEY`).
Default is local Ollama `gemma2:2b`.
```

- [ ] **Step 3: Verify the stack boots**

Run:
```bash
cd /Users/levy/Code/reels/reels-be
docker compose up --build -d
sleep 15
curl -s localhost:8000/api/health
docker compose down
```
Expected: `{"ok":true}`.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml README.md
git commit -m "chore: add docker-compose (postgres + be + fe) with host Ollama"
```

---

## Final verification

- [ ] Backend: `cd reels-be && pytest -v` → all pass.
- [ ] Frontend: `cd reels-fe && npm run build && npm run test` → build + tests pass.
- [ ] Stack: `cd reels-be && docker compose up --build`; open http://localhost:5173, submit a link, confirm it appears in the feed; `curl -X POST localhost:8000/api/scan` and confirm auto items appear with the "Verified Source" badge.
```
