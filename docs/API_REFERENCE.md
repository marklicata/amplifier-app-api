# API Reference - Complete Endpoint Guide

Complete reference for all 23 API endpoints in Amplifier App API.

## Table of Contents

- [Overview](#overview)
- [Sessions (8 endpoints)](#sessions-8-endpoints)
- [Configs (5 endpoints)](#configs-5-endpoints)
- [Applications (5 endpoints)](#applications-5-endpoints)
- [Health & Testing (5 endpoints)](#health--testing-5-endpoints)

---

## Overview

**Total Endpoints:** 23

**Note:** In version 0.3.0, the /bundles, /tools, and /providers registry endpoints were removed. These are now managed directly through config_data when creating/updating configs.

**Base URL:** `http://localhost:8765` (development) or your production domain

**Authentication:** Optional (disabled by default for local dev, enable with `AUTH_REQUIRED=true`)

**Response Format:** JSON (except `/sessions/{id}/stream` which is SSE)

---

## Sessions (8 endpoints)

Sessions are runtime instances that reference a config and maintain conversation state.

### POST /sessions
Create a new session from a config.

**Request:**
```json
{
  "config_id": "c7a3f9e2-1b4d-4c8a-9f2e-d6b8a1c5e3f7"
}
```

**Response:** `201 Created`
```json
{
  "session_id": "s1a2b3c4-5d6e-7f8g-9h0i-1j2k3l4m5n6o",
  "config_id": "c7a3f9e2-1b4d-4c8a-9f2e-d6b8a1c5e3f7",
  "status": "active",
  "message": "Session created successfully"
}
```

---

### GET /sessions
List all sessions (paginated).

**Query Parameters:**
- `limit` (default: 50)
- `offset` (default: 0)

**Response:** `200 OK`
```json
{
  "sessions": [
    {
      "session_id": "...",
      "config_id": "...",
      "status": "active",
      "message_count": 5,
      "created_at": "2026-02-06T12:00:00Z",
      "updated_at": "2026-02-06T12:30:00Z"
    }
  ],
  "total": 10
}
```

---

### GET /sessions/{session_id}
Get session details.

**Response:** `200 OK`
```json
{
  "session_id": "s1a2b3c4-5d6e-7f8g-9h0i-1j2k3l4m5n6o",
  "config_id": "c7a3f9e2-1b4d-4c8a-9f2e-d6b8a1c5e3f7",
  "status": "active"
}
```

**Errors:** `404` if session not found

---

### DELETE /sessions/{session_id}
Delete a session.

**Response:** `200 OK`
```json
{
  "message": "Session deleted successfully"
}
```

---

### POST /sessions/{session_id}/resume
Resume an existing session.

**Response:** `200 OK`
```json
{
  "session_id": "s1a2b3c4-5d6e-7f8g-9h0i-1j2k3l4m5n6o",
  "config_id": "c7a3f9e2-1b4d-4c8a-9f2e-d6b8a1c5e3f7",
  "status": "active",
  "message": "Session resumed successfully"
}
```

---

### POST /sessions/{session_id}/messages
Send a message to a session.

**Request:**
```json
{
  "message": "Create a Python function to calculate fibonacci numbers",
  "context": {}
}
```

**Response:** `200 OK`
```json
{
  "session_id": "s1a2b3c4-5d6e-7f8g-9h0i-1j2k3l4m5n6o",
  "response": "Here's a Python function...",
  "metadata": {
    "config_id": "c7a3f9e2-1b4d-4c8a-9f2e-d6b8a1c5e3f7"
  }
}
```

---

### POST /sessions/{session_id}/stream
Stream message response via Server-Sent Events (SSE).

**Request:** Same as `/messages`

**Response:** `text/event-stream`
```
data: {"type": "connected", "session_id": "..."}

data: {"type": "provider:stream:delta", "data": {"content": "Here"}}

data: {"type": "provider:stream:delta", "data": {"content": "'s"}}

data: {"type": "response", "content": "Here's a Python function..."}

data: {"type": "done"}
```

---

### POST /sessions/{session_id}/cancel
Cancel current operation in a session.

**Response:** `200 OK`
```json
{
  "message": "Cancellation requested"
}
```

---

## Configs (5 endpoints)

Configs are complete YAML bundles that define everything needed for an Amplifier session.

### POST /configs
Create a new config.

**Request:**
```json
{
  "name": "my-config",
  "description": "Development configuration",
  "yaml_content": "bundle:\n  name: dev-bundle\n  version: 1.0.0\n\nincludes:\n  - bundle: foundation\n\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: ${ANTHROPIC_API_KEY}\n      model: claude-sonnet-4-5\n\nsession:\n  orchestrator: loop-basic\n  context: context-simple\n",
  "tags": {
    "env": "dev"
  }
}
```

**Response:** `201 Created`
```json
{
  "config_id": "c7a3f9e2-1b4d-4c8a-9f2e-d6b8a1c5e3f7",
  "name": "my-config",
  "description": "Development configuration",
  "yaml_content": "...",
  "created_at": "2026-02-06T12:00:00Z",
  "updated_at": "2026-02-06T12:00:00Z",
  "tags": {"env": "dev"},
  "message": "Config created successfully"
}
```

**Validation:**
- `bundle.name` is required
- YAML must be valid syntax
- YAML must be a dict

---

### GET /configs
List all configs.

**Query Parameters:**
- `limit` (default: 50)
- `offset` (default: 0)

**Response:** `200 OK`
```json
{
  "configs": [
    {
      "config_id": "...",
      "name": "my-config",
      "description": "...",
      "created_at": "...",
      "updated_at": "...",
      "tags": {}
    }
  ],
  "total": 1
}
```

---

### GET /configs/{config_id}
Get a specific config (includes full YAML).

**Response:** `200 OK`
```json
{
  "config_id": "c7a3f9e2-1b4d-4c8a-9f2e-d6b8a1c5e3f7",
  "name": "my-config",
  "description": "Development configuration",
  "yaml_content": "bundle:\n  name: dev-bundle\n...",
  "created_at": "2026-02-06T12:00:00Z",
  "updated_at": "2026-02-06T12:00:00Z",
  "tags": {"env": "dev"}
}
```

---

### PUT /configs/{config_id}
Update a config (partial or full update).

**Request:** (all fields optional)
```json
{
  "name": "updated-name",
  "description": "Updated description",
  "yaml_content": "bundle:\n  name: updated-bundle\n...",
  "tags": {"env": "production"}
}
```

**Response:** `200 OK`
```json
{
  "config_id": "...",
  "name": "updated-name",
  "description": "Updated description",
  "yaml_content": "...",
  "created_at": "...",
  "updated_at": "2026-02-06T13:00:00Z",
  "tags": {"env": "production"},
  "message": "Config updated successfully"
}
```

---

### DELETE /configs/{config_id}
Delete a config.

**Response:** `200 OK`
```json
{
  "message": "Config deleted successfully"
}
```

---

## Applications (5 endpoints)

Application management for multi-tenant API access.

### POST /applications
Register a new application.

**Request:**
```json
{
  "app_id": "my-mobile-app",
  "app_name": "My Mobile App"
}
```

**Response:** `201 Created`
```json
{
  "app_id": "my-mobile-app",
  "app_name": "My Mobile App",
  "api_key": "app_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "is_active": true,
  "created_at": "2026-02-06T12:00:00Z"
}
```

**⚠️ Important:** Save the `api_key` - it won't be shown again!

---

### GET /applications
List all applications (without API keys).

**Response:** `200 OK`
```json
[
  {
    "app_id": "my-mobile-app",
    "app_name": "My Mobile App",
    "is_active": true,
    "created_at": "...",
    "updated_at": "..."
  }
]
```

---

### GET /applications/{app_id}
Get application details.

**Response:** `200 OK` (without API key)

---

### DELETE /applications/{app_id}
Delete an application.

**Response:** `200 OK`

---

### POST /applications/{app_id}/regenerate-key
Regenerate API key for an application.

**Response:** `200 OK`
```json
{
  "app_id": "my-mobile-app",
  "app_name": "My Mobile App",
  "api_key": "app_NEW_KEY_HERE",
  "is_active": true,
  "created_at": "...",
  "message": "API key regenerated successfully"
}
```

**⚠️ The old API key stops working immediately!**

---

## Health & Testing (5 endpoints)

Service health checks and automated testing.

### GET /
Root endpoint with service information.

**Response:** `200 OK`
```json
{
  "service": "Amplifier App api",
  "version": "0.4.0",
  "description": "REST API service for Amplifier AI development platform",
  "docs": "/docs",
  "health": "/health"
}
```

---

### GET /health
Service health check.

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "version": "0.4.0",
  "uptime": "Days: 0, Hours: 1, Minutes: 23, Seconds: 45",
  "database_connected": true
}
```

---

### GET /version
Version information for service and dependencies.

**Response:** `200 OK`
```json
{
  "service_version": "0.4.0",
  "amplifier_core_version": "976fb87...",
  "amplifier_foundation_version": "412fcb5..."
}
```

---

### GET /smoke-tests/quick
Run quick smoke tests (7 critical tests, <5 seconds).

**Response:** `200 OK`
```json
{
  "timestamp": 123456.789,
  "tests": [
    {"name": "health_endpoint", "passed": true},
    {"name": "database_connectivity", "passed": true},
    {"name": "sessions_endpoint", "passed": true},
    {"name": "config_endpoint", "passed": true},
    {"name": "bundles_endpoint", "passed": true},
    {"name": "applications_endpoint", "passed": true},
    {"name": "application_registration", "passed": true}
  ],
  "passed": 7,
  "failed": 0,
  "success": true,
  "total": 7
}
```

---

### GET /smoke-tests
Run full smoke test suite via pytest.

**Query Parameters:**
- `verbose` (default: false)
- `pattern` (default: "test_smoke.py")

**Response:** `200 OK`
```json
{
  "success": true,
  "exit_code": 0,
  "stdout": "...",
  "summary": {...}
}
```

---

## Complete Endpoint Summary

| Category | Count | Endpoints |
|----------|-------|-----------|
| **Sessions** | 8 | POST, GET, GET/{id}, DELETE/{id}, POST/{id}/resume, POST/{id}/messages, POST/{id}/stream, POST/{id}/cancel |
| **Configs** | 5 | POST, GET, GET/{id}, PUT/{id}, DELETE/{id} |
| **Applications** | 5 | POST, GET, GET/{id}, DELETE/{id}, POST/{id}/regenerate-key |
| **Tools** | 5 | POST, GET, GET/{name}, DELETE/{name}, POST/invoke |
| **Providers** | 4 | POST, GET, GET/{name}, DELETE/{name} |
| **Bundles** | 5 | POST, GET, GET/{name}, DELETE/{name}, POST/{name}/activate |
| **Health** | 5 | GET /, GET /health, GET /version, GET /smoke-tests/quick, GET /smoke-tests |
| **TOTAL** | **37** | |

---

## Common Workflows

### Workflow 1: Create Config and Session
```bash
# 1. Create config
CONFIG_ID=$(curl -s -X POST http://localhost:8765/configs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-config",
    "yaml_content": "bundle:\n  name: my-bundle\n\nincludes:\n  - bundle: foundation\n\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: ${ANTHROPIC_API_KEY}\n      model: claude-sonnet-4-5\n"
  }' | jq -r '.config_id')

# 2. Create session
SESSION_ID=$(curl -s -X POST http://localhost:8765/sessions \
  -H "Content-Type: application/json" \
  -d "{\"config_id\": \"$CONFIG_ID\"}" | jq -r '.session_id')

# 3. Send message
curl -X POST "http://localhost:8765/sessions/$SESSION_ID/messages" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!"}'
```

### Workflow 2: Register and Use Components
```bash
# 1. Register provider
curl -X POST 'http://localhost:8765/providers?name=anthropic&module=provider-anthropic'

# 2. Register tools
curl -X POST 'http://localhost:8765/tools?name=tool-web&source=builtin&module=tool-web'

# 3. Create config using registered components
curl -X POST http://localhost:8765/configs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "registry-config",
    "yaml_content": "bundle:\n  name: my-bundle\n\nincludes:\n  - bundle: foundation\n\nproviders:\n  - module: provider-anthropic\n\ntools:\n  - module: tool-web\n"
  }'
```

### Workflow 3: Update Existing Config
```bash
# 1. Get current config
CURRENT=$(curl -s http://localhost:8765/configs/$CONFIG_ID)

# 2. Update with new YAML
curl -X PUT "http://localhost:8765/configs/$CONFIG_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "yaml_content": "bundle:\n  name: my-bundle\n  version: 2.0.0\n\n[... updated YAML ...]"
  }'
```

---

## Error Responses

All endpoints return standard error responses:

### 400 Bad Request
Invalid input or validation error.
```json
{
  "detail": "Invalid YAML syntax: ..."
}
```

### 404 Not Found
Resource doesn't exist.
```json
{
  "detail": "Config not found"
}
```

### 422 Validation Error
Pydantic validation failed.
```json
{
  "detail": [
    {
      "loc": ["body", "message"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 500 Internal Server Error
Server-side error.
```json
{
  "detail": "Failed to prepare bundle from config: ..."
}
```

---

## Interactive Documentation

**Swagger UI:** http://localhost:8765/docs

**ReDoc:** http://localhost:8765/redoc

**OpenAPI JSON:** http://localhost:8765/openapi.json

---

## Related Documentation

- [CONFIG_API.md](./CONFIG_API.md) - Detailed config API documentation
- [TESTING_AUTHENTICATION.md](./TESTING_AUTHENTICATION.md) - Authentication setup
- [TESTING.md](./TESTING.md) - Comprehensive testing guide

---

**Version:** 0.4.0
**Last Updated:** 2026-02-11
