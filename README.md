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
