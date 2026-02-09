#!/bin/bash
# Development startup script for Amplifier App api

set -e
cd /mnt/c/Users/malicata/source/amplifier-app-api

echo "🚀 Starting Amplifier App api Development Server"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "✅ Created .env - please edit with your API keys"
    echo ""
fi

# Check if local forks exist
if [ ! -d "../amplifier-core" ]; then
    echo "❌ amplifier-core not found at ../amplifier-core"
    echo "Please clone your fork of amplifier-core to the parent directory"
    exit 1
fi

if [ ! -d "../amplifier-foundation" ]; then
    echo "❌ amplifier-foundation not found at ../amplifier-foundation"
    echo "Please clone your fork of amplifier-foundation to the parent directory"
    exit 1
fi

echo "✅ Local forks found"
echo "   - amplifier-core: $(cd ../amplifier-core && git rev-parse --short HEAD)"
echo "   - amplifier-foundation: $(cd ../amplifier-foundation && git rev-parse --short HEAD)"
echo ""

# Check if dependencies are installed (check for FastAPI)
if ! .venv/bin/python -c "import fastapi" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    uv pip install fastapi uvicorn pydantic pydantic-settings pyyaml httpx python-multipart aiosqlite --link-mode=copy
    echo ""
fi

echo "🌐 Starting server at http://localhost:8765"
echo "📚 API docs will be available at http://localhost:8765/docs"
echo ""

# Start the service with auto-reload using uvicorn directly
# No need for editable install - just run the module
PYTHONPATH=/mnt/c/Users/malicata/source/amplifier-app-api:$PYTHONPATH \
.venv/bin/python -m uvicorn amplifier_app_api.main:app --reload --host 0.0.0.0 --port 8765
