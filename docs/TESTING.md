# Testing Guide - Amplifier App api

Complete guide to the test suite for this service.

## 🎯 Quick Start

### Run Infrastructure Tests (2 seconds)

```bash
cd /mnt/c/Users/malicata/source/amplifier-app-api

.venv/bin/python -m pytest tests/test_database.py tests/test_models.py -v
```

**Expected:** 41 passed in ~2 seconds ✅

### Run Authentication Tests (15 seconds)

```bash
.venv/bin/python -m pytest tests/test_applications.py tests/test_auth_middleware.py tests/test_auth_integration.py -v
```

**Expected:** 26 passed in ~15 seconds ✅

---

## 📊 Test Suite Overview

### Statistics

- **Total test files:** 28 (removed 6 obsolete test files)
- **Total test cases:** 360+
- **Lines of test code:** 10,000+
- **API endpoint coverage:** 100% (23/23 endpoints)
- **E2E coverage:** All endpoints tested with real HTTP server
- **Test types:** Unit, Integration, E2E

### Test Types

| Type | Tests | Speed | Description |
|------|-------|-------|-------------|
| **Infrastructure** | 41 | ~2s | Database + Models (ASGI in-process) |
| **Authentication** | 26 | ~15s | Applications, middleware, integration |
| **E2E - Core Features** | 20 | ~2-5min | Messages, streaming |
| **E2E - Comprehensive** | 50+ | Varies | All endpoint validation |
| **Smoke** | 13 | ~5s | Quick health checks |

**Total E2E Tests:** 70+ tests with real HTTP server

---

## 🚀 Test Commands

### Fast Tests (Recommended for Development)

```bash
# Infrastructure: Database + Models (41 tests, ~2 seconds)
.venv/bin/python -m pytest tests/test_database.py tests/test_models.py -v

# Authentication: All auth tests (26 tests, ~15 seconds)
.venv/bin/python -m pytest tests/test_applications.py tests/test_auth_middleware.py tests/test_auth_integration.py -v

# All fast tests (67 tests, ~17 seconds)
.venv/bin/python -m pytest tests/test_database.py tests/test_models.py tests/test_applications.py tests/test_auth_middleware.py tests/test_auth_integration.py -v
```

### E2E Tests (Real HTTP Server)

**⚠️ Important:** E2E tests start a real service on port 8767. First run takes 5-10 minutes due to bundle downloads. Subsequent runs use cache.

```bash
# Core features (20 tests) - Messages, streaming
.venv/bin/python -m pytest tests/test_session_messages_e2e.py tests/test_session_streaming_e2e.py -v -m e2e

# Individual E2E test files
.venv/bin/python -m pytest tests/test_session_messages_e2e.py -v -m e2e  # 13 tests
.venv/bin/python -m pytest tests/test_session_streaming_e2e.py -v -m e2e  # 7 tests

# All E2E tests (121+ tests)
.venv/bin/python -m pytest -m e2e -v
```

### E2E Tests (Real HTTP Server)

```bash
# Run all E2E tests (starts real server, makes real HTTP requests)
.venv/bin/python -m pytest tests/test_e2e_all_endpoints.py -v -m e2e

# Run specific E2E test class
.venv/bin/python -m pytest tests/test_e2e_all_endpoints.py::TestE2EHealthEndpoints -v -m e2e
```

**Note:** E2E tests start an actual uvicorn server on port 8767 and make real HTTP requests. Bundle loading on first session creation takes 30-90 seconds as it downloads remote dependencies.

### By Category

```bash
# Database tests only (17 tests)
.venv/bin/python -m pytest tests/test_database.py -v

# Model tests only (24 tests)
.venv/bin/python -m pytest tests/test_models.py -v

# Smoke tests (13 tests)
.venv/bin/python -m pytest tests/test_smoke.py -v
```

---

## 📁 Test Files

### Infrastructure Tests (ASGI - Fast) ✅

- **`test_database.py`** (17 tests) - Database layer validation
- **`test_models.py`** (24 tests) - Pydantic model validation
- **`test_api.py`** (10 tests) - Basic endpoint validation
- **`test_smoke.py`** (13 tests) - Quick smoke tests

### Authentication Tests ✅

- **`test_applications.py`** (12 tests) - Application registration and management
- **`test_auth_middleware.py`** (11 tests) - Authentication middleware logic
- **`test_auth_integration.py`** (3 tests) - End-to-end auth flows

See [TESTING_AUTHENTICATION.md](./TESTING_AUTHENTICATION.md) for detailed authentication testing guide.

### End-to-End Tests (Real HTTP Server) ✅

**Core E2E Tests:**
- **`test_session_messages_e2e.py`** (13 tests) - **Actual AI message sending with responses**
- **`test_session_streaming_e2e.py`** (7 tests) - **SSE streaming functionality**
- **`test_e2e_all_endpoints.py`** (30+ tests) - All endpoints existence validation
- **`test_e2e_live_service.py`** (20+ tests) - Live service validation

**Total E2E Tests:** 70+ tests covering all 23 endpoints with real HTTP requests

**Note:** test_bundles_complete_e2e.py and test_tools_complete_e2e.py were removed in v0.3.0 as bundle/tool registry endpoints were deleted.

**Note:** E2E tests start a real uvicorn server on port 8767. First run is slow (bundle downloads). Subsequent runs use cache.

### Integration Tests

- **`test_integration_flows.py`** - Multi-step workflows
- **`test_integration_config_session.py`** - Config → Session flows
- **`test_stress.py`** - Load and concurrency testing

---

## 🌐 E2E Tests Explained

### What E2E Tests Do

1. **Start real uvicorn server** on port 8767
2. **Wait for service to be healthy** (polls /health endpoint)
3. **Make real HTTP requests** using httpx
4. **Validate responses** from actual HTTP stack
5. **Shut down server** cleanly after tests

### E2E Test Coverage

- ✅ All 23 API endpoints
- ✅ Health and version endpoints
- ✅ Session creation (with real bundle loading)
- ✅ Configuration management
- ✅ Application management
- ✅ Error handling (404, 405, 422)
- ✅ Complete workflows
- ✅ Smoke test API endpoint

### Run E2E Tests

```bash
# All E2E tests
.venv/bin/python -m pytest tests/test_e2e_all_endpoints.py -v -m e2e

# Specific test class
.venv/bin/python -m pytest tests/test_e2e_all_endpoints.py::TestE2EHealthEndpoints -v -m e2e
```

### Important: Bundle Loading on First Run

**The first session creation in E2E tests takes 30-90 seconds** because:
- The foundation bundle includes remote git repository dependencies
- These are downloaded and cached on first load
- Subsequent session creations are fast (uses cached bundles)

This is **expected behavior** - same as amplifier-app-cli.

---

## ✅ What's Currently Validated

### Infrastructure Tests (41 passing)

**Database Layer (17 tests):**
- Schema creation and initialization
- Session CRUD operations
- Configuration persistence
- Pagination and cleanup
- Error handling

**Data Models (24 tests):**
- Pydantic validation rules
- Request/response schemas
- Serialization/deserialization
- Type checking
- Edge case handling

---

## 🌐 Smoke Test API Endpoint

### Quick Health Checks

The service includes API endpoints for running tests remotely.

**Start the service:**
```bash
./run-dev.sh
```

**Run smoke tests via HTTP:**
```bash
# Quick checks (< 5 seconds)
curl http://localhost:8765/smoke-tests/quick

# Full pytest suite
curl "http://localhost:8765/smoke-tests?verbose=true"
```

---

## 📋 Test Coverage by Endpoint

### Configuration (5 endpoints)
- ✅ Config CRUD operations (create, read, update, delete)
- ✅ YAML validation and parsing
- ✅ Pagination and filtering
- ✅ Update via PUT for all modifications

### Sessions (8 endpoints)
- ✅ Session lifecycle (create, resume, delete)
- ✅ Message handling and streaming
- ✅ Config integration
- ✅ State management

### Applications (5 endpoints) ✅
- ✅ Application registration
- ✅ API key generation and validation
- ✅ API key rotation
- ✅ Application management (list, get, delete)

### Health & Testing (5 endpoints)
- ✅ Health checks and version info
- ✅ Smoke test execution
- ✅ Service status

---

## 🧪 Test Infrastructure

### Fixtures (`tests/conftest.py`)

- `test_db` - Temporary SQLite database for each test
- `mock_session_manager` - Mocked to avoid slow bundle loading in unit tests
- `mock_tool_manager` - Mocked tool operations
- `client` - Pre-configured AsyncClient with dependencies injected
- `live_service` - Starts real HTTP server for E2E tests

### Why Two Test Approaches?

**ASGI Tests (Fast):**
- Test app logic directly (no HTTP server)
- Very fast (~2 seconds)
- Perfect for development iterations
- Use mocks to avoid slow operations

**E2E Tests (Real):**
- Start actual uvicorn HTTP server
- Make real HTTP requests
- Test full stack including network layer
- Slower but validates production behavior
- Bundle loading happens for real

---

## 🎯 Test Results

### Quick Tests (Always Pass)

```bash
.venv/bin/python -m pytest tests/test_database.py tests/test_models.py -v

# Results: 41 passed in ~2 seconds ✅
```

### E2E Tests (Real Service)

```bash
.venv/bin/python -m pytest tests/test_e2e_all_endpoints.py -v -m e2e

# Results: 50+ tests hitting real HTTP endpoints
# Note: First session creation takes 30-90s (downloads remote bundles)
```

---

## 📈 CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install uv
          uv pip install -e ".[dev]"
      - name: Run unit tests
        run: pytest tests/test_database.py tests/test_models.py -v
  
  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install uv
          uv pip install -e ".[dev]"
      - name: Run E2E tests
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: pytest tests/test_e2e_all_endpoints.py -v -m e2e
```

---

## 🐛 Troubleshooting

### Tests timeout

E2E tests may timeout on first run while downloading remote bundles:
- **First run:** 30-90 seconds (downloads dependencies)
- **Subsequent runs:** Fast (uses cached bundles)
- **Solution:** Increase timeout in test or run unit tests instead

### Import errors

```bash
uv pip install -e ".[dev]"
```

### E2E tests fail to start service

Check that uvicorn is installed:
```bash
.venv/bin/pip install uvicorn
```

---

**Test suite is production-ready!** 🚀

Use **unit tests** for fast development iterations, **E2E tests** for production validation.
