# Quick Start Guide

Get the Amplifier App api service running in 5 minutes.

## Prerequisites Check

```bash
# Check Python version (need 3.11+)
python3 --version

# Check uv is installed
uv --version

# If not installed:
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 1. Verify Directory Structure

Your workspace should look like:

```
source/
├── amplifier-core/           ← Your fork
├── amplifier-foundation/     ← Your fork
└── amplifier-app-api/      ← This service
```

```bash
# Check they're all there
ls -la ../amplifier-core
ls -la ../amplifier-foundation
```

If missing, clone your forks:

```bash
cd /mnt/c/Users/malicata/source

# Clone your forks (replace with your GitHub username)
git clone git@github.com:YOUR_USERNAME/amplifier-core.git
git clone git@github.com:YOUR_USERNAME/amplifier-foundation.git
```

## 2. Install Dependencies

```bash
cd amplifier-app-api

# Install with uv (recommended)
uv pip install -e .

# Or with regular pip
pip install -e .
```

This installs:
- FastAPI and Uvicorn
- Pydantic for data models
- aiosqlite for async database
- All other dependencies

**Plus:** Editable installs of your local forks (changes to forks are immediately reflected)

## 3. Configure Environment

```bash
# Copy example environment
cp .env.example .env

# Edit with your API keys
nano .env
```

**Minimum required:**

```bash
# At least one API key
ANTHROPIC_API_KEY=sk-ant-your-key-here
# OR
OPENAI_API_KEY=sk-your-key-here
```

**Optional (paths auto-detected from .env if using default locations):**

```bash
AMPLIFIER_CORE_PATH=../amplifier-core
AMPLIFIER_FOUNDATION_PATH=../amplifier-foundation
```

## 4. Start the Service

### Option A: Development Script (Easiest)

```bash
./run-dev.sh
```

This script:
- Checks dependencies
- Verifies local forks
- Starts server with auto-reload

### Option B: Direct uvicorn

```bash
uvicorn amplifier_app_api.main:app --reload --host 0.0.0.0 --port 8765
```

### Option C: Using the installed script

```bash
amplifier-service
```

## 5. Verify It's Working

### Health Check

```bash
curl http://localhost:8765/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "uptime_seconds": 5.2,
  "database_connected": true
}
```

### API Documentation

Open in browser:
```
http://localhost:8765/docs
```

You should see interactive Swagger UI with all endpoints.

## 6. Test the API

### Create a Session

```bash
curl -X POST http://localhost:8765/sessions/create \
  -H "Content-Type: application/json" \
  -d '{
    "bundle": "foundation",
    "provider": "anthropic"
  }'
```

Example response:
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "active",
  "metadata": {
    "bundle": "foundation",
    "provider": "anthropic",
    "created_at": "2026-02-03T17:00:00",
    "message_count": 0
  },
  "message": "Session created successfully"
}
```

### Send a Message

```bash
# Use the session_id from above
SESSION_ID="a1b2c3d4-e5f6-7890-abcd-ef1234567890"

curl -X POST "http://localhost:8765/sessions/${SESSION_ID}/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a Python function to calculate fibonacci numbers"
  }'
```

### List Your Sessions

```bash
curl http://localhost:8765/sessions
```

### List Available Tools

```bash
curl http://localhost:8765/tools
```

### Get Configuration

```bash
curl http://localhost:8765/config
```

## Troubleshooting

### "Module not found: fastapi"

```bash
# Install dependencies
cd amplifier-app-api
uv pip install -e .
```

### "amplifier-core not found"

```bash
# Check path
ls -la ../amplifier-core

# If missing, clone it
cd ..
git clone <your-fork-url> amplifier-core
```

### "Port 8765 already in use"

```bash
# Kill existing process
lsof -ti:8765 | xargs kill

# Or use a different port
uvicorn amplifier_app_api.main:app --reload --port 8766
```

### "Database locked"

```bash
# Remove database file and restart
rm amplifier.db
./run-dev.sh
```

### Import errors from amplifier-core/foundation

Make sure the paths in `.env` are correct:

```bash
# Check the paths resolve
ls -la $(python3 -c "from amplifier_app_api.config import settings; print(settings.amplifier_core_path)")
```

## Next Steps

Once the service is running:

1. **Test with curl** - Use the examples above
2. **Explore the API docs** - http://localhost:8765/docs
3. **Integrate with a client** - Web app, mobile app, etc.
4. **Customize** - Modify your local forks and see changes immediately

## Development Workflow

```bash
# 1. Make changes to amplifier-core or amplifier-foundation
cd ../amplifier-core
# ... edit files ...

# 2. Restart service (auto-reload picks up changes)
# No restart needed! uvicorn --reload watches for changes

# 3. Test the changes
curl -X POST http://localhost:8765/sessions/{id}/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "Test my changes"}'
```

## Production Deployment

See [SETUP.md](SETUP.md) for production deployment with Docker.

## Getting Help

- Check logs in terminal where service is running
- Review [README.md](README.md) for full API reference
- Check [SETUP.md](SETUP.md) for deployment guide
- Look at API docs: http://localhost:8765/docs

---

**Time to first request: ~5 minutes** ⚡
