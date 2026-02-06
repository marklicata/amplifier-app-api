# Configuration API Documentation

The Configuration API provides CRUD operations for managing Amplifier bundle configurations. Configs are stored in PostgreSQL and contain complete YAML bundle definitions that can be used to start sessions.

## Table of Contents

- [Overview](#overview)
- [Storage](#storage)
- [Core Endpoints](#core-endpoints)
  - [Create Config](#create-config)
  - [List Configs](#list-configs)
  - [Get Config](#get-config)
  - [Update Config](#update-config)
  - [Delete Config](#delete-config)
- [Validation Rules](#validation-rules)
- [Examples](#examples)

## Overview

A **config** is a complete YAML bundle configuration that defines:
- Bundle metadata (name, version, description)
- Included bundles (via `includes`)
- Providers (LLM backends like Anthropic, OpenAI)
- Tools (filesystem, bash, web, etc.)
- Optional: session orchestrator, context manager, hooks, agents

Configs are:
- **Reusable**: Create once, use for multiple sessions
- **Persistent**: Stored in PostgreSQL database
- **Flexible**: Can rely on included bundles for session configuration
- **Programmatically modifiable**: Helper endpoints let you add tools, providers, and bundles dynamically

## Storage

Configs are stored in the **PostgreSQL database** in the `configs` table:

| Column | Type | Description |
|--------|------|-------------|
| `config_id` | TEXT (UUID) | Unique identifier |
| `name` | VARCHAR(255) | Human-readable name |
| `description` | TEXT | Optional description |
| `yaml_content` | TEXT | Complete YAML bundle |
| `created_at` | TIMESTAMPTZ | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | Last update timestamp |
| `tags` | JSONB | Key-value tags for filtering |

## Core Endpoints

### Create Config

Create a new config with YAML bundle content.

**Endpoint:** `POST /configs`

**Request Body:**
```json
{
  "name": "my-config",
  "description": "Optional description",
  "yaml_content": "bundle:\n  name: my-bundle\n  version: 1.0.0\n",
  "tags": {
    "env": "dev",
    "team": "platform"
  }
}
```

**Response:** `201 Created`
```json
{
  "config_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "my-config",
  "description": "Optional description",
  "yaml_content": "bundle:\n  name: my-bundle\n  version: 1.0.0\n",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "tags": {
    "env": "dev",
    "team": "platform"
  },
  "message": "Config created successfully"
}
```

**Validation:**
- `name` is required
- `yaml_content` is required and must be valid YAML
- YAML must contain a `bundle` section with a `name` field
- `session`, `orchestrator`, `context` are optional (can come from includes)

**Example:**
```bash
curl -X POST http://localhost:8765/configs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "development",
    "description": "Development configuration",
    "yaml_content": "bundle:\n  name: dev-bundle\n  version: 1.0.0\n\nincludes:\n  - bundle: git+https://github.com/microsoft/amplifier-foundation@main\n\nproviders:\n  - module: provider-anthropic\n    config:\n      default_model: claude-sonnet-4-5-20250929\n",
    "tags": {
      "env": "dev"
    }
  }'
```

---

### List Configs

Get a paginated list of all configs (metadata only, without full YAML content).

**Endpoint:** `GET /configs`

**Query Parameters:**
- `limit` (optional, default: 50) - Maximum number of configs to return
- `offset` (optional, default: 0) - Offset for pagination

**Response:** `200 OK`
```json
{
  "configs": [
    {
      "config_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "development",
      "description": "Development configuration",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z",
      "tags": {
        "env": "dev"
      }
    }
  ],
  "total": 1
}
```

**Example:**
```bash
# Get first 10 configs
curl http://localhost:8765/configs?limit=10&offset=0

# Get next 10 configs
curl http://localhost:8765/configs?limit=10&offset=10
```

---

### Get Config

Get a specific config by ID (includes full YAML content).

**Endpoint:** `GET /configs/{config_id}`

**Response:** `200 OK`
```json
{
  "config_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "development",
  "description": "Development configuration",
  "yaml_content": "bundle:\n  name: dev-bundle\n...",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "tags": {
    "env": "dev"
  }
}
```

**Errors:**
- `404 Not Found` - Config does not exist

**Example:**
```bash
curl http://localhost:8765/configs/550e8400-e29b-41d4-a716-446655440000
```

---

### Update Config

Update an existing config. You can update any combination of fields.

**Endpoint:** `PUT /configs/{config_id}`

**Request Body (all fields optional):**
```json
{
  "name": "new-name",
  "description": "Updated description",
  "yaml_content": "bundle:\n  name: updated-bundle\n",
  "tags": {
    "env": "production"
  }
}
```

**Response:** `200 OK`
```json
{
  "config_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "new-name",
  "description": "Updated description",
  "yaml_content": "bundle:\n  name: updated-bundle\n",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T11:00:00Z",
  "tags": {
    "env": "production"
  },
  "message": "Config updated successfully"
}
```

**Notes:**
- Only fields you provide will be updated
- If you update `yaml_content`, it will be validated
- Updating `yaml_content` invalidates the bundle cache for any active sessions

**Errors:**
- `404 Not Found` - Config does not exist
- `400 Bad Request` - Invalid YAML or validation error

**Example:**
```bash
# Update only the description
curl -X PUT http://localhost:8765/configs/550e8400-e29b-41d4-a716-446655440000 \
  -H "Content-Type: application/json" \
  -d '{"description": "New description"}'
```

---

### Delete Config

Delete a config permanently.

**Endpoint:** `DELETE /configs/{config_id}`

**Response:** `200 OK`
```json
{
  "message": "Config deleted successfully"
}
```

**Errors:**
- `404 Not Found` - Config does not exist

**Notes:**
- This operation cannot be undone
- Sessions using this config will fail if you try to resume them

**Example:**
```bash
curl -X DELETE http://localhost:8765/configs/550e8400-e29b-41d4-a716-446655440000
```

---

## Validation Rules

When creating or updating configs, the YAML content is validated:

### Required Validation
- ✅ YAML must be valid syntax
- ✅ YAML must be a dictionary/object (not a scalar or list)
- ✅ Must have a `bundle` section
- ✅ `bundle.name` must be a non-empty string

### Optional Sections
The following sections are **optional** because they can be provided by included bundles:
- `session` - Session configuration
- `session.orchestrator` - Orchestrator type
- `session.context` - Context manager type
- `providers` - LLM providers
- `tools` - Available tools
- `hooks` - Event hooks
- `agents` - Agent definitions
- `spawn` - Spawn policy

### Invalid Examples

❌ **Missing bundle section:**
```yaml
providers:
  - module: provider-anthropic
```
Error: `Missing required section: 'bundle'`

❌ **Missing bundle.name:**
```yaml
bundle:
  version: 1.0.0
```
Error: `Missing required field: 'bundle.name'`

❌ **Invalid YAML syntax:**
```yaml
bundle:
  name: test
    invalid: indentation
```
Error: `Invalid YAML syntax: ...`

❌ **YAML is not a dict:**
```yaml
just a string
```
Error: `YAML content must be a dictionary/object, not a scalar value`

### Valid Minimal Example

✅ **Minimal valid config:**
```yaml
bundle:
  name: my-minimal-config
  version: 1.0.0

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main
```

This is valid because `amplifier-foundation` provides the `session`, `orchestrator`, and `context` configuration.

---

## Examples

### Example 1: Complete Development Config

```yaml
bundle:
  name: development-config
  version: 1.0.0
  description: Complete development configuration with all components

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main

providers:
  - module: provider-anthropic
    source: git+https://github.com/microsoft/amplifier-module-provider-anthropic@main
    config:
      default_model: claude-sonnet-4-5-20250929
      enable_1m_context: false
      priority: 1

tools:
  - module: tool-filesystem
  - module: tool-bash
  - module: tool-web
    source: git+https://github.com/microsoft/amplifier-tool-web@main

instructions:
  You are a helpful development assistant with access to filesystem, bash, and web tools.
```

### Example 2: Minimal Config Relying on Includes

```yaml
bundle:
  name: minimal-config
  version: 1.0.0

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main
  - bundle: git+https://github.com/microsoft-amplifier/amplifier-shared@main#subdirectory=bundles/product-management

providers:
  - module: provider-anthropic
    config:
      default_model: claude-sonnet-4-5-20250929

instructions:
  You are a product management assistant.
```

### Example 3: Building a Config Programmatically

```bash
#!/bin/bash

# 1. Create minimal config
CONFIG_ID=$(curl -s -X POST http://localhost:8765/configs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "programmatic-config",
    "yaml_content": "bundle:\n  name: programmatic\n  version: 1.0.0\n",
    "tags": {"env": "dev"}
  }' | jq -r '.config_id')

echo "Created config: $CONFIG_ID"

# 2. Add foundation bundle
curl -X POST http://localhost:8765/configs/$CONFIG_ID/bundles \
  -H "Content-Type: application/json" \
  -d '{"bundle_uri": "git+https://github.com/microsoft/amplifier-foundation@main"}'

# 3. Add Anthropic provider
curl -X POST http://localhost:8765/configs/$CONFIG_ID/providers \
  -H "Content-Type: application/json" \
  -d '{
    "provider_module": "provider-anthropic",
    "provider_config": {
      "default_model": "claude-sonnet-4-5-20250929",
      "api_key": "${ANTHROPIC_API_KEY}"
    }
  }'

# 4. Add tools
curl -X POST http://localhost:8765/configs/$CONFIG_ID/tools \
  -H "Content-Type: application/json" \
  -d '{"tool_module": "tool-filesystem", "tool_source": "builtin"}'

curl -X POST http://localhost:8765/configs/$CONFIG_ID/tools \
  -H "Content-Type: application/json" \
  -d '{"tool_module": "tool-bash", "tool_source": "builtin"}'

# 5. Get the final config
curl http://localhost:8765/configs/$CONFIG_ID | jq '.yaml_content'
```

### Example 4: Creating a Config from UI

```javascript
// Frontend code example
async function createConfig(name, description, tags) {
  // Create minimal config
  const response = await fetch('/configs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      description,
      yaml_content: `bundle:\n  name: ${name}\n  version: 1.0.0\n`,
      tags
    })
  });

  const config = await response.json();
  const configId = config.config_id;

  // Add foundation bundle
  await fetch(`/configs/${configId}/bundles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      bundle_uri: 'git+https://github.com/microsoft/amplifier-foundation@main'
    })
  });

  // Add provider
  await fetch(`/configs/${configId}/providers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      provider_module: 'provider-anthropic',
      provider_config: {
        default_model: 'claude-sonnet-4-5-20250929'
      }
    })
  });

  return configId;
}
```

---

## Related Documentation

- [Session API](./SESSION_API.md) - Create and manage sessions using configs
- [Bundle API](./BUNDLE_API.md) - Global bundle registry (separate from configs)
- [Tools API](./TOOLS_API.md) - List and invoke tools from bundles
- [PostgreSQL Migration](./POSTGRESQL_MIGRATION_SUMMARY.md) - Database schema and migration guide
