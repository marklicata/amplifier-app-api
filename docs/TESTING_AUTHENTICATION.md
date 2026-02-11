# Authentication Testing Guide

This guide provides step-by-step instructions for testing the authentication system in `amplifier-app-api`.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start: Running All Tests](#quick-start-running-all-tests)
3. [Manual Testing with cURL](#manual-testing-with-curl)
4. [Testing with Python Requests](#testing-with-python-requests)
5. [Test Coverage](#test-coverage)
6. [Troubleshooting](#troubleshooting)

---

## Overview

The authentication system supports two modes:

1. **API Key + JWT** (Recommended): Applications authenticate with API keys, users with JWTs
2. **JWT Only**: Both app and user identified from JWT claims

**Default Development Mode**: Authentication is **disabled** (`AUTH_REQUIRED=false`) for easier local development.

### GitHub Authentication in Dev Mode (NEW)

When authentication is disabled (`AUTH_REQUIRED=false`), the system now automatically uses your **GitHub identity** from the `gh` CLI instead of a hardcoded `"dev-user"`:

- ✅ **If `gh` CLI is installed and authenticated**: Uses your GitHub username (e.g., `marklicata`)
- ✅ **If `gh` CLI is not available**: Falls back to `"dev-user"`
- ✅ **Zero configuration**: Works automatically if you're logged into GitHub CLI
- ✅ **Better testing**: Each developer gets their own `user_id` without auth setup

**To disable this feature**, set `USE_GITHUB_AUTH_IN_DEV=false` in your `.env` file.

---

## Quick Start: Running All Tests

### 1. Install Dependencies

```bash
# Install project with dev dependencies
uv pip install -e ".[dev]"
```

### 2. Run All Authentication Tests

```bash
# Run all auth tests
pytest tests/test_applications.py tests/test_auth_middleware.py tests/test_auth_integration.py -v

# Or run specific test file
pytest tests/test_applications.py -v
pytest tests/test_auth_middleware.py -v
pytest tests/test_auth_integration.py -v
```

### 3. Run with Coverage

```bash
# Generate coverage report
pytest tests/test_applications.py tests/test_auth_middleware.py tests/test_auth_integration.py --cov=amplifier_app_api --cov-report=html

# View coverage report
open htmlcov/index.html
```

---

## Manual Testing with cURL

### Scenario 1: Development Mode (Auth Disabled)

**Default `.env` setting**: `AUTH_REQUIRED=false`

```bash
# Start service
python -m amplifier_app_api.main

# All endpoints work without authentication
curl http://localhost:8765/sessions
curl http://localhost:8765/configs
curl http://localhost:8765/health
```

✅ **Expected**: All requests succeed without any auth headers.

**What `user_id` is used?**
- If you're logged into GitHub CLI (`gh auth status` shows ✓): Your GitHub username
- If not logged in or `gh` not installed: `"dev-user"`
- To always use `"dev-user"`: Set `USE_GITHUB_AUTH_IN_DEV=false` in `.env`

```bash
# Check what user_id you're using:
gh auth status
# If logged in, your GitHub username will be used
# To see which user created a session, check the session response

# To force dev-user instead of GitHub username:
echo "USE_GITHUB_AUTH_IN_DEV=false" >> .env
```

---

### Scenario 2: Production Mode (Auth Enabled)

**Update `.env`**: Set `AUTH_REQUIRED=true`

```bash
# Restart service with auth enabled
export AUTH_REQUIRED=true
python -m amplifier_app_api.main
```

#### Step 1: Register an Application

```bash
curl -X POST http://localhost:8765/applications \
  -H "Content-Type: application/json" \
  -d '{
    "app_id": "test-app",
    "app_name": "Test Application"
  }'
```

✅ **Expected Response**:
```json
{
  "app_id": "test-app",
  "app_name": "Test Application",
  "api_key": "app_xxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "is_active": true,
  "created_at": "2026-02-05T17:00:00Z",
  "message": "Application registered successfully"
}
```

🔑 **SAVE THE API KEY** - You won't see it again!

#### Step 2: Create a JWT for Testing

For development, create a test JWT using your `SECRET_KEY` from `.env`:

**Python script** (`create_test_jwt.py`):
```python
import jwt
from datetime import datetime, timedelta

SECRET_KEY = "your-secret-key-here-generate-a-new-one"  # From .env
user_id = "test-user-123"

# Create JWT valid for 1 hour
token = jwt.encode(
    {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(hours=1)
    },
    SECRET_KEY,
    algorithm="HS256"
)

print(f"JWT Token: {token}")
```

Run it:
```bash
python create_test_jwt.py
```

#### Step 3: Make Authenticated Requests

```bash
# Set your credentials
API_KEY="app_xxxxxxxxxxxxxxxxxxxxxxxxxxx"  # From step 1
JWT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."  # From step 2

# List sessions (authenticated)
curl http://localhost:8765/sessions \
  -H "X-API-Key: $API_KEY" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

✅ **Expected**: Request succeeds (200 OK).

#### Step 4: Test Auth Failures

**Missing API Key**:
```bash
curl http://localhost:8765/sessions \
  -H "Authorization: Bearer $JWT_TOKEN"
```
❌ **Expected**: 401 Unauthorized - "Missing X-API-Key header"

**Missing JWT**:
```bash
curl http://localhost:8765/sessions \
  -H "X-API-Key: $API_KEY"
```
❌ **Expected**: 401 Unauthorized - "Missing or invalid Authorization header"

**Invalid API Key**:
```bash
curl http://localhost:8765/sessions \
  -H "X-API-Key: invalid-key" \
  -H "Authorization: Bearer $JWT_TOKEN"
```
❌ **Expected**: 401 Unauthorized - "Invalid API key"

**Expired JWT**:
```python
# Create expired JWT
expired_token = jwt.encode(
    {"sub": "user", "exp": 1},  # Expired in 1970
    SECRET_KEY,
    algorithm="HS256"
)
```
```bash
curl http://localhost:8765/sessions \
  -H "X-API-Key: $API_KEY" \
  -H "Authorization: Bearer $EXPIRED_TOKEN"
```
❌ **Expected**: 401 Unauthorized - "JWT expired"

---

## Testing with Python Requests

### Complete Auth Flow Example

Save as `test_auth_flow.py`:

```python
import requests
import jwt
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8765"
SECRET_KEY = "your-secret-key-here-generate-a-new-one"  # From .env

# Step 1: Register application
print("1. Registering application...")
app_response = requests.post(
    f"{BASE_URL}/applications",
    json={
        "app_id": "my-test-app",
        "app_name": "My Test Application"
    }
)
app_data = app_response.json()
api_key = app_data["api_key"]
print(f"   API Key: {api_key[:20]}...")

# Step 2: Create JWT
print("2. Creating JWT...")
user_id = "python-test-user"
token = jwt.encode(
    {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(hours=1)
    },
    SECRET_KEY,
    algorithm="HS256"
)
print(f"   JWT: {token[:50]}...")

# Step 3: Make authenticated request
print("3. Making authenticated request...")
headers = {
    "X-API-Key": api_key,
    "Authorization": f"Bearer {token}"
}

# Create a config
config_response = requests.post(
    f"{BASE_URL}/configs",
    json={
        "name": "test-config",
        "yaml_content": """
bundle:
  name: test
includes:
  - bundle: foundation
session:
  orchestrator: loop-basic
  context: context-simple
providers:
  - module: provider-anthropic
    config:
      api_key: test-key
      model: claude-sonnet-4-5
"""
    },
    headers=headers
)

if config_response.status_code == 201:
    print("   ✓ Config created successfully!")
    config_id = config_response.json()["config_id"]
    
    # Create a session
    session_response = requests.post(
        f"{BASE_URL}/sessions",
        json={"config_id": config_id},
        headers=headers
    )
    
    if session_response.status_code in [201, 200]:
        print("   ✓ Session created successfully!")
    else:
        print(f"   ✗ Session creation failed: {session_response.status_code}")
        print(f"     {session_response.json()}")
else:
    print(f"   ✗ Config creation failed: {config_response.status_code}")
    print(f"     {config_response.json()}")

# Step 4: List applications
print("4. Listing applications...")
apps_response = requests.get(f"{BASE_URL}/applications")
print(f"   Found {len(apps_response.json())} applications")

# Step 5: Test with invalid credentials
print("5. Testing invalid credentials...")
bad_response = requests.get(
    f"{BASE_URL}/sessions",
    headers={"X-API-Key": "invalid-key", "Authorization": f"Bearer {token}"}
)
if bad_response.status_code == 401:
    print("   ✓ Invalid API key correctly rejected")
else:
    print(f"   ✗ Expected 401, got {bad_response.status_code}")

print("\nTest complete!")
```

Run it:
```bash
# Make sure AUTH_REQUIRED=true in .env
export AUTH_REQUIRED=true
python -m amplifier_app_api.main &

# Wait for service to start
sleep 2

# Run test
python test_auth_flow.py
```

---

## Test Coverage

### Application Management (`test_applications.py`)

✅ **Creates and manages applications**
- Register new application
- Duplicate app_id rejection
- Invalid app_id format validation
- List applications
- Get application details
- Delete application
- Regenerate API key
- API key format validation
- API key hashing in database
- Settings persistence

**Run**: `pytest tests/test_applications.py -v`

---

### Authentication Middleware (`test_auth_middleware.py`)

✅ **Validates authentication logic**
- Public paths bypass auth
- Auth disabled mode (dev)
- Missing API key rejection
- Missing JWT rejection
- Invalid API key rejection
- Valid API key + JWT acceptance
- Expired JWT rejection
- JWT missing `sub` claim rejection
- Malformed JWT rejection
- JWT-only mode with app_id claim
- Disabled application rejection
- Request state population
- JWT issuer validation
- JWT audience validation

**Run**: `pytest tests/test_auth_middleware.py -v`

---

### Integration Tests (`test_auth_integration.py`)

✅ **End-to-end auth flows**
- Full auth flow: register → create JWT → make request
- Session tracking with user_id and app_id
- Cross-app session access
- Different users cannot access each other's sessions
- JWT-only mode integration
- API key rotation workflow
- Multiple concurrent users
- Clear error messages

**Run**: `pytest tests/test_auth_integration.py -v`

---

## Troubleshooting

### Issue: Tests fail with "Database not connected"

**Solution**: Tests use `test_db` fixture which creates a temporary database. Make sure you're using the `client` fixture:

```python
@pytest.mark.asyncio
async def test_my_endpoint(client: AsyncClient, test_db):
    # client fixture already sets up test_db
    response = await client.get("/endpoint")
```

---

### Issue: "Import 'httpx' could not be resolved"

**Solution**: This is a type-checking issue. Runtime works fine. Install dev dependencies:

```bash
uv pip install -e ".[dev]"
```

---

### Issue: Authentication always passes in tests

**Solution**: Tests run with `AUTH_REQUIRED=false` by default. Use `patch` to enable auth:

```python
from unittest.mock import patch
from amplifier_app_api.config import settings

with patch.object(settings, "auth_required", True):
    # Auth is enabled in this block
    response = await client.get("/sessions", headers=auth_headers)
```

---

### Issue: JWT signature verification fails

**Solution**: Make sure you're using the same `SECRET_KEY` from `.env`:

```python
from amplifier_app_api.config import settings

token = jwt.encode(
    {"sub": "user", "exp": 9999999999},
    settings.secret_key,  # Use settings.secret_key
    algorithm="HS256"
)
```

---

### Issue: "Application already exists" in tests

**Solution**: Each test gets a fresh database via the `test_db` fixture. If you see this error, you're creating the same app_id twice in one test:

```python
# Wrong - creates duplicate
await client.post("/applications", json={"app_id": "test", ...})
await client.post("/applications", json={"app_id": "test", ...})  # ❌

# Right - use unique IDs
await client.post("/applications", json={"app_id": "test-1", ...})
await client.post("/applications", json={"app_id": "test-2", ...})  # ✅
```

---

## Production Deployment Checklist

Before deploying to production with authentication enabled:

- [ ] Set `AUTH_REQUIRED=true` in production `.env`
- [ ] Generate strong `SECRET_KEY`: `openssl rand -hex 32`
- [ ] Configure `JWT_ALGORITHM=RS256` for production
- [ ] Set `JWT_PUBLIC_KEY_URL` to your auth provider's JWKS endpoint
- [ ] Set `JWT_ISSUER` to expected issuer claim
- [ ] Set `JWT_AUDIENCE` to your API's audience
- [ ] Register production applications via `/applications` endpoint
- [ ] Store API keys securely (environment variables, secret manager)
- [ ] Test auth flow end-to-end in staging environment
- [ ] Monitor authentication failures in production logs
- [ ] Set up alerts for high auth failure rates

---

## Quick Reference

### Environment Variables

```bash
# Authentication
AUTH_REQUIRED=false              # Enable/disable auth
AUTH_MODE=api_key_jwt           # api_key_jwt | jwt_only
USE_GITHUB_AUTH_IN_DEV=true     # Use gh CLI for user_id in dev mode
API_KEY_HEADER=X-API-Key        # Header name for API key

# JWT Settings
JWT_ALGORITHM=HS256             # HS256 (dev) | RS256 (prod)
JWT_PUBLIC_KEY_URL=             # JWKS endpoint (RS256 only)
JWT_ISSUER=                     # Expected 'iss' claim
JWT_AUDIENCE=                   # Expected 'aud' claim
SECRET_KEY=                     # Secret for HS256 (generate new!)
```

### Test Commands

```bash
# Run all auth tests
pytest tests/test_applications.py tests/test_auth_middleware.py tests/test_auth_integration.py -v

# Run specific test
pytest tests/test_applications.py::test_create_application -v

# Run with coverage
pytest tests/test_applications.py --cov=amplifier_app_api.api.applications --cov-report=term

# Run tests matching pattern
pytest -k "test_auth" -v
```

### cURL Templates

```bash
# Register application
curl -X POST http://localhost:8765/applications \
  -H "Content-Type: application/json" \
  -d '{"app_id": "my-app", "app_name": "My App"}'

# Make authenticated request
curl http://localhost:8765/sessions \
  -H "X-API-Key: app_xxxx" \
  -H "Authorization: Bearer eyJhbG..."

# List applications
curl http://localhost:8765/applications

# Regenerate API key
curl -X POST http://localhost:8765/applications/my-app/regenerate-key
```

---

## Additional Resources

- [AUTHENTICATION_DESIGN.md](../AUTHENTICATION_DESIGN.md) - Complete auth architecture
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/) - Framework docs
- [JWT.io](https://jwt.io) - JWT debugger and docs
- [PyJWT Documentation](https://pyjwt.readthedocs.io/) - Python JWT library

---

**Last Updated**: 2026-02-05  
**Version**: 1.0.0
