#!/bin/bash
# Verification script to test Railway setup

set -e

echo "🔍 Verifying Reels Backend Setup for Railway..."
echo ""

# Check Python version
echo "✓ Python version:"
python --version

# Check dependencies
echo ""
echo "✓ Checking dependencies..."
pip list | grep -E "fastapi|sqlalchemy|apscheduler|psycopg2"

# Check Docker
echo ""
echo "✓ Docker version:"
docker --version

# Check environment file
echo ""
echo "✓ Environment configuration:"
if [ -f ".env" ]; then
    echo "  .env found"
    grep -E "^[A-Z_]+" .env | head -5
else
    echo "  ⚠️  .env not found (copy .env.example or .env.railway)"
fi

# Check entrypoint
echo ""
if [ -f "entrypoint.sh" ]; then
    echo "✓ Entrypoint script found"
    head -3 entrypoint.sh
else
    echo "❌ Entrypoint script missing"
    exit 1
fi

# Check Dockerfile
echo ""
echo "✓ Dockerfile configuration:"
grep -E "HEALTHCHECK|EXPOSE" Dockerfile

# Test imports
echo ""
echo "✓ Testing Python imports..."
python -c "
import sys
try:
    from app.config import get_settings
    from app.db import get_engine, SessionLocal
    from app.llm.factory import get_provider
    from app.scheduler import start_scheduler
    print('  All imports successful!')
except Exception as e:
    print(f'  ❌ Import failed: {e}')
    sys.exit(1)
"

echo ""
echo "✅ Setup verification complete!"
echo ""
echo "Next steps:"
echo "1. Set environment variables: cp .env.railway .env"
echo "2. Start locally: docker-compose up"
echo "3. Test backend: curl http://localhost:8000/api/health"
echo "4. Deploy to Railway: railway up"
