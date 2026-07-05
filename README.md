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

## Hourly AI-news scan

A background scheduler runs every hour (`SCAN_CRON=0 * * * *`), pulls the RSS
sources in `sources.config.json`, and for each new item asks the configured LLM
(Ollama by default) to split the topic into two layers:

- **`short_summary`** — a one-line blurb shown on the feed card at a glance.
- **`long_summary`** — a deeper explanation revealed by "see more" in the UI.

Both are stored on `feed_items` alongside the title, image, and `source_url`,
so the frontend can render title → short → see-more → source link. If the model
call fails the scan never crashes — it falls back to the raw feed excerpt.

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
