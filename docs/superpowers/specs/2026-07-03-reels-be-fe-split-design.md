# Design: Split reels monorepo into `reels-be` (FastAPI) + `reels-fe` (React reels UI)

**Date:** 2026-07-03
**Status:** Approved

## 1. Goal

Split the current single full-stack repo (`reels-fe/`, an Express+React monolith) into two
independent repos:

- **`reels-be/`** — Python/FastAPI backend (rewritten from the old Node/TS server).
- **`reels-fe/`** — React/Vite frontend, rebuilt as a full-screen TikTok/Reels-style feed.

End state resembles the reference product ("ReelAkamai — your company, in a swipe"): a
mobile-first vertical scroll-snap feed of AI/ML content, backed by a local Ollama model.

## 2. Scope (v1)

**In:**
- Feed API with like/view engagement.
- X.com scheduled auto-ingestion (bypasses any moderation, per PRD).
- RSS/HTML auto-scanner (ported from the old Node scanner) → LLM summarize → insert.
- Reddit + YouTube content types rendered as native embeds.
- LLM = local Ollama `gemma2:2b`, with optional external providers (anthropic/openai).
- Local orchestration via docker-compose (Ollama on host).

**Out (v1):**
- Webex bot ingestion + AI gatekeeper.
- Akamai EAA authentication (a `status`/review stub is kept so it can be added later).

## 3. Architecture

Two independent git repos communicating over HTTP.

- Backend exposes REST under `/api/*`, enables CORS for the frontend origin.
- Frontend reads `VITE_API_BASE_URL` to locate the backend.
- Single Postgres database owned by the backend.
- APScheduler runs scheduled ingestion jobs inside the FastAPI lifespan.

### Split mechanics
- `reels-be/` (currently empty except `.git`) → fresh FastAPI project.
- `reels-fe/` → move `client/*` to the repo root; **delete `server/`** (logic ported to Python);
  rewrite `api.ts` for a configurable base URL. `sources.config.json` moves into `reels-be`.
- Keep the existing dark theme, PWA manifest, service worker, and generated icons in `reels-fe`.

## 4. Backend structure (Python/FastAPI)

```
reels-be/
  app/
    main.py          lifespan: migrate -> start scheduler -> mount routers + CORS
    config.py        pydantic-settings (env)
    db.py            SQLAlchemy engine/session + idempotent migrate
    models.py        FeedItem, MonitoredXAccount, Source
    schemas.py       pydantic request/response
    routers/feed.py  GET /api/feed, POST /api/feed, /{id}/view, /{id}/like, /health
    llm/             provider protocol + ollama.py / anthropic.py / openai.py + prompts.py
    ingest/
      scraper.py     OG tags + article text (BeautifulSoup)
      dedupe.py      unique hash on source_url
      classify.py    detect content_type from URL (youtube/x/reddit/article)
      rss_scanner.py scheduled: RSS/HTML -> ollama summarize -> insert
      x_sync.py      APScheduler X.com v2 pull (since_id pagination)
    scheduler.py     APScheduler (BackgroundScheduler in lifespan)
  sources.config.json
  Dockerfile
  pyproject.toml
```

## 5. Database schema (Postgres, SQLAlchemy)

**`feed_items`**
- `id` (PK)
- `content_type` — enum: `youtube | x | reddit | article`
- `source_url`
- `dedup_hash` (unique) — hash of source_url (+title) to prevent duplicate inserts
- `title`, `author` (nullable)
- `article_summary` (text, nullable)
- `image_url` (nullable)
- `source_type` — `auto | manual`
- `status` — `draft | published`, default `published`
- `shared_by_name`, `shared_by_email` — e.g. "System Auto-Pull" / "system@company.internal"
- `views` (int, default 0), `likes` (int, default 0)
- `created_at` (default now)

**`monitored_x_accounts`**
- `id` (PK), `x_handle` (unique), `x_user_id`, `last_tweet_id` (nullable), `is_active` (default true)

**`sources`**
- RSS/HTML/reddit scan targets, synced from `sources.config.json` on startup.

`status` is retained so a no-auth review page can be added later. In v1, auto content
(X + RSS) inserts as `published`.

## 6. API contract

- `GET /api/feed?sort_by=date|views|likes&content_type=&limit=` → array of `feed_items`
  (default `sort_by=date`, `limit` capped, published only).
- `POST /api/feed` → manual submit. URL → classify content_type → scrape OG → insert.
  Per-IP rate limited.
- `POST /api/feed/{id}/view` → increment `views` by 1.
- `POST /api/feed/{id}/like` → increment `likes` by 1.
- `GET /api/health` → `{ ok: true }`.

## 7. Frontend (React/Vite reels)

```
reels-fe/src/
  api.ts                base URL from VITE_API_BASE_URL; fetchFeed/view/like/submit
  App.tsx               reels shell + sort control + submit route
  components/
    ReelsFeed.tsx       scroll-snap-y container; IntersectionObserver -> POST view
    Slide.tsx           dispatch renderer by content_type
    YouTubeEmbed.tsx    YouTube IFrame embed (autoplay on scroll where possible)
    XEmbed.tsx          X/Twitter embed
    RedditEmbed.tsx     Reddit embed
    ArticleCard.tsx     dimmed full-bleed image + title + summary + read-more
    Overlay.tsx         heart (like toggle) + AttributionBadge
    SortControl.tsx     date / views / likes
    SubmitForm.tsx      manual URL submit
  styles.css            full-screen slides, scroll-snap-type: y mandatory
```

- **Views:** `IntersectionObserver` fires `POST /api/feed/{id}/view` when a slide is fully visible.
- **Likes:** heart toggle fires `POST /api/feed/{id}/like`.
- **AttributionBadge:** `shared_by_name === 'System Auto-Pull'` → robot icon + gradient/vibrant
  tag ("Verified Source"); otherwise avatar + "Shared by [Name]".

## 8. LLM integration

Provider abstraction with a common interface. Default `MODEL_PROVIDER=ollama`,
`OLLAMA_MODEL=gemma2:2b`, `OLLAMA_BASE_URL=http://host.docker.internal:11434`. External
providers (`anthropic`, `openai`) selectable via env.

Only the RSS/HTML scanner uses the LLM (summarize/extract from scraped article text). X, Reddit,
and YouTube carry structured metadata and skip the LLM. On LLM timeout/error the scanner falls
back to the raw OG description so a slow local model never blocks ingestion.

## 9. Local dev (docker-compose)

One `docker-compose.yml` in `reels-be` (build contexts: `.` for backend, `../reels-fe` for
frontend) brings up **postgres + backend + frontend**. **Ollama runs on the host** (existing
install); containers reach it at `host.docker.internal:11434` via `extra_hosts`. `docker compose
up` starts everything; the frontend targets the backend through `VITE_API_BASE_URL`.

## 10. Error handling & testing

- Scraper/LLM failures skip the individual item and log; a scan never crashes on one bad source.
- `dedup_hash` unique constraint prevents duplicate inserts (insert-or-ignore).
- Manual submit is per-IP rate limited and validates URL scheme.
- **pytest** (backend): feed endpoints, dedupe, URL classify, scraper parse, provider mocked,
  X sync `since_id` logic.
- **vitest** (frontend, light): the `content_type` → renderer dispatch in `Slide.tsx`.

## 11. Deployment note

Production target is Railway (per the existing README). Backend + Postgres as services; Ollama
either as a Railway service with a volume (`gemma2:2b`, ~1.6 GB) or an external LLM API. Frontend
built and served as a static site pointing at the backend URL. Deployment specifics are out of
scope for this spec beyond preserving Railway compatibility.
