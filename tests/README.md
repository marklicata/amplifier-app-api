# Test Suite Guide

## Test Types

### Unit/Integration Tests (Fast - Uses ASGI)
These test the app **in-process** without starting a server:
- `test_database.py` - Database layer
- `test_models.py` - Data models
- `test_smoke.py` - Smoke tests
- `test_sessions_comprehensive.py` - Session APIs
- `test_config_comprehensive.py` - Config APIs
- `test_bundles_comprehensive.py` - Bundle APIs
- `test_tools_comprehensive.py` - Tool APIs
- `test_health_comprehensive.py` - Health APIs
- `test_integration_flows.py` - Multi-step flows
- `test_stress.py` - Load testing

**Pros:** Very fast (~2 seconds for 41 tests)  
**Cons:** Doesn't test actual HTTP server

### End-to-End Tests (Real HTTP Server)
**New:** `test_e2e_live_service.py` - Spins up actual service and makes real HTTP requests

**Pros:** Tests the full stack including uvicorn server  
**Cons:** Slower (~10 seconds to start + test)

---

## Running Tests

### Fast Tests (Recommended)
```bash
# 41 tests in ~2 seconds
.venv/bin/python -m pytest tests/test_database.py tests/test_models.py -v
```

### End-to-End Tests (Real Server)
```bash
# Start real server and test it
.venv/bin/python -m pytest tests/test_e2e_live_service.py -v -m e2e
```

### All Tests
```bash
# Everything (may take time)
.venv/bin/python -m pytest tests/ -v
```

---

## Test Markers

```bash
# Only E2E tests (real server)
.venv/bin/python -m pytest -m e2e -v

# Skip E2E tests (fast tests only)
.venv/bin/python -m pytest -m "not e2e" -v
```

---

**Use E2E tests when:**
- Validating deployment
- Testing CORS configuration
- Verifying full HTTP stack
- Before releases

**Use fast tests when:**
- During development
- Quick validation
- CI/CD pipelines
