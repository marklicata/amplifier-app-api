# Amplifier App api

REST API service for the Amplifier AI development platform. Exposes Amplifier's capabilities through HTTP endpoints for integration with web applications, mobile apps, and other services.

## Overview

This service is based on [amplifier-app-cli](https://github.com/microsoft/amplifier-app-cli) but provides REST API access instead of CLI commands. It uses **local forks** of `amplifier-core` and `amplifier-foundation` for independent development.

**Key Features:**
- 🔌 RESTful API for Amplifier sessions
- 🔐 API Key + JWT authentication (multi-tenant)
- 📊 Application Insights telemetry
- 📦 Bundle and provider management
- 🛠️ Tool invocation endpoints
- 📝 Configuration management with CRUD + helper endpoints
- 💾 PostgreSQL persistence (Azure PostgreSQL)
- 🔄 Server-Sent Events (SSE) for streaming
- 🐳 Docker deployment ready
- 🧪 400+ tests with full endpoint coverage

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
│   │   ├── applications.py  # Application registration
│   │   ├── tools.py      # Tool invocation
│   │   ├── health.py     # Health checks
│   │   └── smoke.py      # Smoke test endpoint
│   ├── core/             # Business logic
│   │   ├── session_manager.py   # Wraps amplifier-core
│   │   ├── config_manager.py    # Config management
│   │   └── tool_manager.py      # Tool operations
│   ├── middleware/       # Middleware
│   │   └── auth.py       # Authentication (API key + JWT)
│   ├── models/           # Pydantic data models
│   │   ├── application.py  # Application models
│   │   ├── user.py         # User models
│   │   └── session.py      # Session models
│   ├── storage/          # Database layer (PostgreSQL)
│   ├── telemetry/        # Application Insights telemetry
│   ├── config.py         # Application settings
│   └── main.py           # FastAPI application
├── tests/                # 400+ test cases
│   ├── test_applications.py  # Auth tests
│   ├── test_auth_middleware.py
│   └── test_auth_integration.py
├── docs/                 # Documentation
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml        # Uses pinned commits
```

## Prerequisites

- Python 3.11+
- [UV](https://github.com/astral-sh/uv) package manager
- Local forks of:
  - `amplifier-core` (at `../amplifier-core`)
  - `amplifier-foundation` (at `../amplifier-foundation`)

## API Endpoints

### Configuration (5 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/configs` | Create a new config (YAML bundle) |
| GET | `/configs` | List all configs |
| GET | `/configs/{id}` | Get config details |
| PUT | `/configs/{id}` | Update config (modify YAML directly) |
| DELETE | `/configs/{id}` | Delete a config |

### Session Management (8 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/sessions` | Create session from config |
| GET | `/sessions` | List all sessions |
| GET | `/sessions/{id}` | Get session details |
| DELETE | `/sessions/{id}` | Delete a session |
| POST | `/sessions/{id}/resume` | Resume existing session |
| POST | `/sessions/{id}/messages` | Send message |
| POST | `/sessions/{id}/stream` | Stream responses (SSE) |
| POST | `/sessions/{id}/cancel` | Cancel operation |

### Application Management (5 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/applications` | Register a new application |
| GET | `/applications` | List all applications |
| GET | `/applications/{id}` | Get application details |
| DELETE | `/applications/{id}` | Delete application |
| POST | `/applications/{id}/regenerate-key` | Regenerate API key |

### Tool Registry (5 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tools` | Register tool in global registry |
| GET | `/tools?from_registry=true` | List tools from registry |
| GET | `/tools/{name}?from_registry=true` | Get tool from registry |
| DELETE | `/tools/{name}` | Remove tool from registry |
| POST | `/tools/invoke` | Invoke a tool |

### Provider Registry (4 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/providers` | Register provider in global registry |
| GET | `/providers` | List all registered providers |
| GET | `/providers/{name}` | Get provider from registry |
| DELETE | `/providers/{name}` | Remove provider from registry |

### Bundle Registry (5 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/bundles` | Register bundle in global registry |
| GET | `/bundles` | List all registered bundles |
| GET | `/bundles/{name}` | Get bundle from registry |
| DELETE | `/bundles/{name}` | Remove bundle from registry |
| POST | `/bundles/{name}/activate` | Set active bundle |

### Health & Testing (5 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health check |
| GET | `/version` | Version information |
| GET | `/` | Service information |
| GET | `/smoke-tests/quick` | Run quick smoke tests |
| GET | `/smoke-tests` | Run full test suite |

**Total: 37 endpoints**

## Usage Examples

### 1. Create a Config (YAML Bundle)

First, create a config that defines your Amplifier setup:

```bash
curl -X POST http://localhost:8765/configs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-dev-config",
    "description": "Development configuration with Anthropic",
    "yaml_content": "bundle:\n  name: dev-config\n  version: 1.0.0\n\nincludes:\n  - bundle: foundation\n\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: ${ANTHROPIC_API_KEY}\n      model: claude-sonnet-4-5\n\nsession:\n  orchestrator: loop-streaming\n  context: context-persistent"
  }'
```

**Response:**
```json
{
  "config_id": "c7a3f9e2-1b4d-4c8a-9f2e-d6b8a1c5e3f7",
  "name": "my-dev-config",
  "description": "Development configuration with Anthropic",
  "yaml_content": "bundle:\n  name: dev-config...",
  "created_at": "2026-02-05T00:00:00Z",
  "updated_at": "2026-02-05T00:00:00Z",
  "tags": {},
  "message": "Config created successfully"
}
```

### 2. Create a Session from Config

Use the config_id to create a session:

```bash
curl -X POST http://localhost:8765/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "config_id": "c7a3f9e2-1b4d-4c8a-9f2e-d6b8a1c5e3f7"
  }'
```

**Response:**
```json
{
  "session_id": "s1a2b3c4-5d6e-7f8g-9h0i-1j2k3l4m5n6o",
  "config_id": "c7a3f9e2-1b4d-4c8a-9f2e-d6b8a1c5e3f7",
  "status": "active",
  "message": "Session created successfully"
}
```

### 3. Send a Message

```bash
curl -X POST http://localhost:8765/sessions/s1a2b3c4-5d6e-7f8g-9h0i-1j2k3l4m5n6o/messages \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a Python function to calculate fibonacci numbers"
  }'
```

**Response:**
```json
{
  "session_id": "s1a2b3c4-5d6e-7f8g-9h0i-1j2k3l4m5n6o",
  "response": "Here's a Python function...",
  "metadata": {
    "config_id": "c7a3f9e2-1b4d-4c8a-9f2e-d6b8a1c5e3f7"
  }
}
```

### 4. Reuse Config for Multiple Sessions

Create another session from the same config:

```bash
curl -X POST http://localhost:8765/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "config_id": "c7a3f9e2-1b4d-4c8a-9f2e-d6b8a1c5e3f7"
  }'
```

**Benefits:**
- Same configuration guaranteed
- Bundle already prepared (instant session creation)
- Parallel conversations with identical setup

## Configuration

### Environment Variables

Create `.env` from `.env.example` and configure:

```bash
# LLM API Keys (required: at least one)
ANTHROPIC_API_KEY=your-key-here
OPENAI_API_KEY=your-key-here

# Service settings
SERVICE_HOST=0.0.0.0
SERVICE_PORT=8765

# Database
DATABASE_URL=sqlite+aiosqlite:///./amplifier.db

# Authentication (disabled by default for local dev)
AUTH_REQUIRED=false                    # Set true for production
AUTH_MODE=api_key_jwt                  # api_key_jwt | jwt_only
USE_GITHUB_AUTH_IN_DEV=true           # Use gh CLI for user_id in dev mode
SECRET_KEY=generate-new-key-here       # openssl rand -hex 32
JWT_ALGORITHM=HS256                    # HS256 (dev) | RS256 (prod)
JWT_PUBLIC_KEY_URL=                    # JWKS endpoint for RS256
JWT_ISSUER=                            # Expected 'iss' claim
JWT_AUDIENCE=                          # Expected 'aud' claim

# Telemetry
TELEMETRY_ENABLED=true
TELEMETRY_APP_INSIGHTS_CONNECTION_STRING=  # From Azure portal
TELEMETRY_APP_ID=amplifier-app-api
TELEMETRY_ENVIRONMENT=development

# Local fork paths
AMPLIFIER_CORE_PATH=../amplifier-core
AMPLIFIER_FOUNDATION_PATH=../amplifier-foundation

# CORS (comma-separated)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
```

### Authentication Setup

**For local development** (default):
- `AUTH_REQUIRED=false` - No authentication needed
- All endpoints accessible without credentials
- **NEW**: Automatically uses your GitHub username from `gh` CLI as `user_id`
  - If `gh auth status` shows you're logged in → Uses your GitHub username
  - If not logged in or `gh` not installed → Falls back to `"dev-user"`
  - To disable: Set `USE_GITHUB_AUTH_IN_DEV=false` in `.env`

**For production**:
1. Set `AUTH_REQUIRED=true`
2. Generate secret key: `openssl rand -hex 32`
3. Register applications to get API keys:
   ```bash
   curl -X POST http://localhost:8765/applications \
     -H "Content-Type: application/json" \
     -d '{"app_id": "my-app", "app_name": "My Application"}'
   ```
4. Include headers in requests:
   ```bash
   curl http://localhost:8765/sessions \
     -H "X-API-Key: app_xxxx" \
     -H "Authorization: Bearer <jwt-token>"
   ```

See [docs/TESTING_AUTHENTICATION.md](docs/TESTING_AUTHENTICATION.md) for complete authentication guide.

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

See [docs/SETUP.md](docs/SETUP.md) for production deployment guide.

## Testing

The service includes a comprehensive test suite with 400+ test cases covering all endpoints and core business logic.

### Run Tests

```bash
# Infrastructure tests (41 tests in ~2 seconds)
.venv/bin/python -m pytest tests/test_database.py tests/test_models.py -v

# Authentication tests (26 tests in ~15 seconds)
.venv/bin/python -m pytest tests/test_applications.py tests/test_auth_middleware.py tests/test_auth_integration.py -v

# All tests
.venv/bin/python -m pytest tests/ -v
```

### Test via API

```bash
# Start service
./run-dev.sh

# Run quick smoke tests (includes auth check)
curl http://localhost:8765/smoke-tests/quick
```

**Test Coverage:**
- ✅ Core business logic: 110+ new comprehensive tests
- ✅ Infrastructure (database, models): 60+ tests
- ✅ Authentication (applications, middleware, integration): 26 tests
- ✅ API endpoints: All 37 endpoints fully tested
- ✅ E2E flows: Config → Session → Message with real HTTP

See [docs/TESTING.md](docs/TESTING.md) and [docs/TESTING_AUTHENTICATION.md](docs/TESTING_AUTHENTICATION.md) for complete guides.

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

### Getting Started
- **[QUICKSTART.md](QUICKSTART.md)** - Get running in 5 minutes
- **[docs/SETUP.md](docs/SETUP.md)** - Production deployment guide

### Features & Architecture
- **[docs/AUTHENTICATION_DESIGN.md](docs/AUTHENTICATION_DESIGN.md)** - Authentication architecture (✅ Implemented)
- **[docs/TELEMETRY_PLAN.md](docs/TELEMETRY_PLAN.md)** - Telemetry architecture (✅ Implemented)

### Testing
- **[docs/TESTING.md](docs/TESTING.md)** - Test suite documentation
- **[docs/TESTING_AUTHENTICATION.md](docs/TESTING_AUTHENTICATION.md)** - Authentication testing guide
- **[docs/TELEMETRY_TESTING.md](docs/TELEMETRY_TESTING.md)** - Telemetry testing guide
- **[docs/MANUAL_TESTING_GUIDE.md](docs/MANUAL_TESTING_GUIDE.md)** - Manual testing procedures

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
