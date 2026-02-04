# Amplifier App api

REST API service for the Amplifier AI development platform. Exposes Amplifier's capabilities through HTTP endpoints for integration with web applications, mobile apps, and other services.

## Overview

This service is based on [amplifier-app-cli](https://github.com/microsoft/amplifier-app-cli) but provides REST API access instead of CLI commands. It uses **local forks** of `amplifier-core` and `amplifier-foundation` for independent development.

**Key Features:**
- 🔌 RESTful API for Amplifier sessions
- 📦 Bundle and provider management
- 🛠️ Tool invocation endpoints
- 📝 Configuration management
- 💾 SQLite-based persistence
- 🔄 Server-Sent Events (SSE) for streaming
- 🐳 Docker deployment ready
- 🧪 164+ tests with 100% endpoint coverage

## Quick Start

See [QUICKSTART.md](QUICKSTART.md) for complete setup instructions (5 minutes).

### Fast Start

```bash
# 1. Install dependencies
cd amplifier-app-api
uv pip install -e .

# 2. Configure API key
cp .env.example .env
nano .env  # Add your ANTHROPIC_API_KEY or OPENAI_API_KEY

# 3. Start service
./run-dev.sh

# 4. Verify
curl http://localhost:8765/health
```

**API Docs:** http://localhost:8765/docs

## Architecture

```
amplifier-app-api/
├── amplifier_app_api/
│   ├── api/              # REST API endpoints
│   │   ├── sessions.py   # Session management
│   │   ├── config.py     # Configuration
│   │   ├── bundles.py    # Bundle management
│   │   ├── tools.py      # Tool invocation
│   │   ├── health.py     # Health checks
│   │   └── smoke.py      # Smoke test endpoint
│   ├── core/             # Business logic
│   │   ├── session_manager.py   # Wraps amplifier-core
│   │   ├── config_manager.py    # Config management
│   │   └── tool_manager.py      # Tool operations
│   ├── models/           # Pydantic data models
│   ├── storage/          # Database layer (SQLite)
│   ├── config.py         # Application settings
│   └── main.py           # FastAPI application
├── tests/                # 164+ test cases
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml        # Uses local forks
```

## Prerequisites

- Python 3.11+
- [UV](https://github.com/astral-sh/uv) package manager
- Local forks of:
  - `amplifier-core` (at `../amplifier-core`)
  - `amplifier-foundation` (at `../amplifier-foundation`)

## API Endpoints

### Session Management (8 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/sessions/create` | Create a new session |
| GET | `/sessions` | List all sessions |
| GET | `/sessions/{id}` | Get session details |
| DELETE | `/sessions/{id}` | Delete a session |
| POST | `/sessions/{id}/resume` | Resume existing session |
| POST | `/sessions/{id}/messages` | Send message |
| POST | `/sessions/{id}/stream` | Stream responses (SSE) |
| POST | `/sessions/{id}/cancel` | Cancel operation |

### Configuration (7 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/config` | Get all configuration |
| POST | `/config` | Update configuration |
| GET | `/config/providers` | List providers |
| POST | `/config/providers` | Add/update provider |
| GET | `/config/providers/{name}` | Get provider config |
| POST | `/config/providers/{name}/activate` | Set active provider |
| GET | `/config/providers/current` | Get active provider |

### Bundles (5 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/bundles` | List all bundles |
| POST | `/bundles` | Add a bundle |
| GET | `/bundles/{name}` | Get bundle details |
| DELETE | `/bundles/{name}` | Remove bundle |
| POST | `/bundles/{name}/activate` | Set active bundle |

### Tools (3 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tools` | List available tools |
| GET | `/tools/{name}` | Get tool information |
| POST | `/tools/invoke` | Invoke a tool |

### Health & Testing (5 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health check |
| GET | `/version` | Version information |
| GET | `/` | Service information |
| GET | `/smoke-tests/quick` | Quick smoke tests via API |
| GET | `/smoke-tests` | Full test suite via API |

**Total: 28 endpoints**

## Usage Examples

### Create a Session

```bash
curl -X POST http://localhost:8765/sessions/create \
  -H "Content-Type: application/json" \
  -d '{
    "bundle": "foundation",
    "provider": "anthropic",
    "model": "claude-sonnet-4-5"
  }'
```

**Response:**
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "active",
  "metadata": {
    "bundle": "foundation",
    "provider": "anthropic",
    "model": "claude-sonnet-4-5",
    "created_at": "2026-02-03T17:00:00",
    "message_count": 0
  },
  "message": "Session created successfully"
}
```

### Send a Message

```bash
curl -X POST http://localhost:8765/sessions/{session_id}/messages \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a Python function to calculate fibonacci numbers"
  }'
```

**Response:**
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "response": "Here's a Python function...",
  "metadata": {
    "provider": "anthropic",
    "model": "claude-sonnet-4-5"
  }
}
```

### Run Smoke Tests

```bash
# Quick health checks
curl http://localhost:8765/smoke-tests/quick
```

**Response:**
```json
{
  "success": true,
  "passed": 4,
  "failed": 0,
  "total": 4,
  "tests": [
    {"name": "health_endpoint", "passed": true},
    {"name": "database_connectivity", "passed": true},
    {"name": "sessions_endpoint", "passed": true},
    {"name": "config_endpoint", "passed": true}
  ]
}
```

## Configuration

### Environment Variables

Create `.env` from `.env.example` and configure:

```bash
# Required: At least one API key
ANTHROPIC_API_KEY=your-key-here
# OR
OPENAI_API_KEY=your-key-here

# Service settings
SERVICE_HOST=0.0.0.0
SERVICE_PORT=8765

# Database
DATABASE_URL=sqlite+aiosqlite:///./amplifier.db

# Local fork paths (default: ../amplifier-core and ../amplifier-foundation)
AMPLIFIER_CORE_PATH=../amplifier-core
AMPLIFIER_FOUNDATION_PATH=../amplifier-foundation

# CORS (comma-separated)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
```

### Using Local Forks

This service uses **editable local forks** instead of published packages:

```toml
[tool.uv.sources]
amplifier-core = { path = "../amplifier-core", editable = true }
amplifier-foundation = { path = "../amplifier-foundation", editable = true }
```

**Benefits:**
- Changes to forks immediately reflected
- Full control over versioning
- Independent development

**Trade-off:**
- Manual upstream syncing required

## Deployment

### Development

```bash
# Using the development script (recommended)
./run-dev.sh

# Or directly with uvicorn
uvicorn amplifier_app_api.main:app --reload --host 0.0.0.0 --port 8765
```

### Docker

```bash
# Using Docker Compose (recommended)
docker-compose up -d

# Or build manually
docker build -t amplifier-app-api .
docker run -p 8765:8765 --env-file .env amplifier-app-api
```

See [SETUP.md](SETUP.md) for production deployment guide.

## Testing

The service includes a comprehensive test suite with 164+ test cases.

### Run Tests

```bash
# Quick tests (41 tests in ~2 seconds)
.venv/bin/python -m pytest tests/test_database.py tests/test_models.py -v

# All tests
.venv/bin/python -m pytest tests/ -v
```

### Test via API

```bash
# Start service
./run-dev.sh

# Run smoke tests via HTTP
curl http://localhost:8765/smoke-tests/quick
```

See [TESTING.md](TESTING.md) for complete testing guide.

## Differences from amplifier-app-cli

| Feature | amplifier-app-cli | amplifier-app-api |
|---------|-------------------|---------------------|
| **Interface** | CLI commands | REST API endpoints |
| **Usage** | `amplifier run "prompt"` | `curl -X POST /sessions/{id}/messages` |
| **Dependencies** | Published packages | Local editable forks |
| **Session storage** | Filesystem (JSONL) | SQLite database |
| **Streaming** | Terminal output | Server-Sent Events (SSE) |
| **Deployment** | Local install | Docker container / web service |

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Get running in 5 minutes
- **[SETUP.md](SETUP.md)** - Production deployment guide
- **[TESTING.md](TESTING.md)** - Test suite documentation
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Architecture and design

## Troubleshooting

### "Database not connected" error

The database auto-initializes on first request. If you see this error, verify the database path is writable.

### "amplifier-core not found" error

Verify local fork paths:
```bash
ls -la ../amplifier-core
ls -la ../amplifier-foundation
```

Update paths in `.env` if different.

### Port already in use

```bash
# Change port in .env
SERVICE_PORT=8766

# Or kill existing process
lsof -ti:8765 | xargs kill
```

### Import errors

```bash
# Reinstall dependencies
cd amplifier-app-api
uv pip install -e .
```

## Contributing

This is a custom service for specific deployment needs. If building something similar, fork and customize for your use case.

## License

MIT License (same as amplifier-app-cli)

## Related Projects

- [amplifier-core](https://github.com/microsoft/amplifier-core) - Amplifier kernel
- [amplifier-foundation](https://github.com/microsoft/amplifier-foundation) - Foundation library  
- [amplifier-app-cli](https://github.com/microsoft/amplifier-app-cli) - CLI reference implementation

---

**Built with ❤️ using Amplifier**
