#!/bin/bash
set -e

echo "🚀 Starting reels backend..."

# Wait for PostgreSQL to be ready
if [ -n "$DATABASE_URL" ]; then
    echo "⏳ Waiting for PostgreSQL..."
    DB_HOST=$(echo $DATABASE_URL | grep -oP '(?<=@)[^:]+' || echo "localhost")
    DB_PORT=$(echo $DATABASE_URL | grep -oP '(?<=:)[0-9]+(?=/)' || echo "5432")

    max_attempts=30
    attempt=1
    while [ $attempt -le $max_attempts ]; do
        if pg_isready -h "$DB_HOST" -p "$DB_PORT" 2>/dev/null; then
            echo "✅ PostgreSQL is ready!"
            break
        fi
        echo "   Attempt $attempt/$max_attempts: PostgreSQL not ready, waiting..."
        sleep 2
        attempt=$((attempt + 1))
    done

    if [ $attempt -gt $max_attempts ]; then
        echo "❌ PostgreSQL failed to become ready after $max_attempts attempts"
        exit 1
    fi
fi

echo "🗄️  Running database migrations..."
python -c "
from app.db import migrate
from app.ingest.sources import sync_sources
from app.ingest.x_accounts import sync_x_accounts

migrate()
sync_sources()
sync_x_accounts()
print('✅ Migrations complete')
"

echo "🤖 Starting scheduler and API server..."
exec uvicorn app.main:app --host :: --port 8000
