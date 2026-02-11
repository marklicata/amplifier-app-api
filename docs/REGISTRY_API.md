# Global Registry API Documentation

## ⚠️ DEPRECATED - Removed in v0.3.0

**This document describes functionality that was removed in version 0.3.0.**

The global registry endpoints (`/tools`, `/providers`, `/bundles`) have been removed to simplify the API.

### What Changed

**Before (v0.2.x):**
- Register tools/providers/bundles in global registries via API endpoints
- Reference registered components when creating configs

**Now (v0.3.0+):**
- Specify tools/providers directly in `config_data` when creating configs
- Each config is self-contained with all necessary module sources
- No separate registration step needed

### Migration Guide

Instead of:
```bash
# OLD: Register provider first
POST /providers?name=anthropic-prod&module=provider-anthropic

# Then reference it
POST /configs
{
  "providers": [{"module": "anthropic-prod"}]
}
```

Now do:
```bash
# NEW: Include provider directly in config
POST /configs
{
  "config_data": {
    "providers": [{
      "module": "provider-anthropic",
      "source": "git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
      "config": {"api_key": "...", "model": "claude-sonnet-4-5"}
    }]
  }
}
```

See [API_REFERENCE.md](API_REFERENCE.md) for current endpoints.

---

## Historical Documentation (Pre-v0.3.0)

The following documentation describes the registry API as it existed before v0.3.0:

### Overview (Historical)

The Global Registry API provided centralized management for tools, providers, and bundles across the Amplifier platform. These registries allowed you to:

1. **Discover** available components
2. **Register** new components for reuse
3. **Reference** registered components when building configs

## Table of Contents

- [Overview](#overview)
- [Storage](#storage)
- [Tool Registry](#tool-registry)
- [Provider Registry](#provider-registry)
- [Bundle Registry](#bundle-registry)
- [Integration with Configs](#integration-with-configs)
- [Examples](#examples)

## Overview

### What are Registries?

Registries are **global catalogs** of reusable components:

| Registry | Purpose | Example Use Case |
|----------|---------|------------------|
| **Tools** | Register tools (filesystem, web, bash, custom) | "Register tool-custom so all configs can use it" |
| **Providers** | Register LLM providers (Anthropic, OpenAI, Azure) | "Register anthropic-prod with production settings" |
| **Bundles** | Register bundle packages | "Register foundation bundle for quick reference" |

### Registries vs Configs

| Concept | Scope | Storage | Purpose |
|---------|-------|---------|---------|
| **Registry** | Global | `configuration` table | Discovery & reuse |
| **Config** | Per-config | `configs` table | Session definition |

**Workflow:**
1. **Register** a tool/provider in the global registry
2. **Reference** it when creating or modifying configs
3. **Use** the config to start sessions

## Storage

All registries are stored in the PostgreSQL `configuration` table as JSONB key-value pairs:

| Key | Value | Description |
|-----|-------|-------------|
| `"tools"` | `{name: {source, module, ...}}` | Tool registry |
| `"providers"` | `{name: {module, source, ...}}` | Provider registry |
| `"bundles"` | `{name: {source, scope, ...}}` | Bundle registry |

## Tool Registry

Manage the global tool registry for discovering and registering tools.

### Register Tool

**Endpoint:** `POST /tools`

**Query Parameters:**
- `name` (required) - Tool name/alias
- `source` (required) - Tool source URI (git URL, "builtin", or path)
- `module` (optional) - Tool module identifier (defaults to name)
- `description` (optional) - Tool description
- `config` (optional, JSON body) - Default tool configuration

**Example:**
```bash
curl -X POST 'http://localhost:8765/tools?name=tool-custom&source=git+https://github.com/example/tool-custom@main&description=My custom tool' \
  -H "Content-Type: application/json" \
  -d '{"timeout": 30, "max_retries": 3}'
```

**Response:** `201 Created`
```json
{
  "message": "Tool 'tool-custom' registered successfully",
  "name": "tool-custom",
  "source": "git+https://github.com/example/tool-custom@main"
}
```

---

### List Tools from Registry

**Endpoint:** `GET /tools?from_registry=true`

**Query Parameters:**
- `from_registry=true` - List from global registry (not bundle inspection)

**Example:**
```bash
curl 'http://localhost:8765/tools?from_registry=true'
```

**Response:** `200 OK`
```json
{
  "tools": [
    {
      "name": "tool-custom",
      "description": "My custom tool",
      "parameters": {}
    },
    {
      "name": "tool-web",
      "description": "Web scraping tool",
      "parameters": {}
    }
  ]
}
```

---

### Get Tool from Registry

**Endpoint:** `GET /tools/{tool_name}?from_registry=true`

**Query Parameters:**
- `from_registry=true` - Get from global registry (not bundle inspection)

**Example:**
```bash
curl 'http://localhost:8765/tools/tool-custom?from_registry=true'
```

**Response:** `200 OK`
```json
{
  "name": "tool-custom",
  "source": "git+https://github.com/example/tool-custom@main",
  "module": "tool-custom",
  "description": "My custom tool",
  "config": {
    "timeout": 30,
    "max_retries": 3
  }
}
```

---

### Delete Tool from Registry

**Endpoint:** `DELETE /tools/{tool_name}`

**Example:**
```bash
curl -X DELETE http://localhost:8765/tools/tool-custom
```

**Response:** `200 OK`
```json
{
  "message": "Tool 'tool-custom' removed from registry successfully"
}
```

---

## Provider Registry

Manage the global provider registry for discovering and registering LLM providers.

### Register Provider

**Endpoint:** `POST /providers`

**Query Parameters:**
- `name` (required) - Provider name/alias
- `module` (required) - Provider module identifier (e.g., "provider-anthropic")
- `source` (optional) - Provider source URI (omit for installed packages)
- `description` (optional) - Provider description
- `config` (optional, JSON body) - Default provider configuration

**Example:**
```bash
curl -X POST 'http://localhost:8765/providers?name=anthropic-prod&module=provider-anthropic&source=git+https://github.com/microsoft/amplifier-module-provider-anthropic@main&description=Production Anthropic provider' \
  -H "Content-Type: application/json" \
  -d '{
    "default_model": "claude-sonnet-4-5-20250929",
    "priority": 1,
    "api_key": "${ANTHROPIC_API_KEY}"
  }'
```

**Response:** `201 Created`
```json
{
  "message": "Provider 'anthropic-prod' registered successfully",
  "name": "anthropic-prod",
  "module": "provider-anthropic"
}
```

---

### List Providers from Registry

**Endpoint:** `GET /providers`

**Example:**
```bash
curl http://localhost:8765/providers
```

**Response:** `200 OK`
```json
{
  "anthropic-prod": {
    "module": "provider-anthropic",
    "source": "git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
    "description": "Production Anthropic provider",
    "config": {
      "default_model": "claude-sonnet-4-5-20250929",
      "priority": 1,
      "api_key": "${ANTHROPIC_API_KEY}"
    }
  },
  "openai-dev": {
    "module": "provider-openai",
    "source": null,
    "description": "Development OpenAI provider",
    "config": {
      "model": "gpt-4"
    }
  }
}
```

---

### Get Provider from Registry

**Endpoint:** `GET /providers/{provider_name}`

**Example:**
```bash
curl http://localhost:8765/providers/anthropic-prod
```

**Response:** `200 OK`
```json
{
  "name": "anthropic-prod",
  "module": "provider-anthropic",
  "source": "git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
  "description": "Production Anthropic provider",
  "config": {
    "default_model": "claude-sonnet-4-5-20250929",
    "priority": 1,
    "api_key": "${ANTHROPIC_API_KEY}"
  }
}
```

---

### Delete Provider from Registry

**Endpoint:** `DELETE /providers/{provider_name}`

**Example:**
```bash
curl -X DELETE http://localhost:8765/providers/anthropic-prod
```

**Response:** `200 OK`
```json
{
  "message": "Provider 'anthropic-prod' removed from registry successfully"
}
```

---

## Bundle Registry

See [Bundle API Documentation](./BUNDLE_API.md) for complete bundle registry details.

**Quick Reference:**
- `POST /bundles` - Register a bundle
- `GET /bundles` - List all bundles
- `GET /bundles/{name}` - Get bundle details
- `DELETE /bundles/{name}` - Remove bundle
- `POST /bundles/{name}/activate` - Set active bundle

---

## Integration with Configs

Registries integrate with config operations to enable reusable components.

### Workflow: Register → Reference → Use

```bash
# 1. Register components in global registries (for discovery)
curl -X POST 'http://localhost:8765/tools?name=tool-web&source=git+https://example.com/tool-web&module=tool-web&description=Web tool'
curl -X POST 'http://localhost:8765/providers?name=anthropic&module=provider-anthropic&description=Anthropic provider'
curl -X POST 'http://localhost:8765/bundles' -d '{"name": "foundation", "source": "git+..."}'

# 2. Create a config with components from registry
CONFIG_ID=$(curl -s -X POST http://localhost:8765/configs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-config",
    "yaml_content": "bundle:\n  name: my-bundle\n  version: 1.0.0\n\nincludes:\n  - bundle: foundation\n\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: ${ANTHROPIC_API_KEY}\n      model: claude-sonnet-4-5\n\ntools:\n  - module: tool-web\n    source: git+https://example.com/tool-web\n\nsession:\n  orchestrator: loop-basic\n  context: context-simple\n"
  }' | jq -r '.config_id')

# 3. Use the config to create a session
curl -X POST http://localhost:8765/sessions \
  -H "Content-Type: application/json" \
  -d "{\"config_id\": \"$CONFIG_ID\"}"
```

---

## Examples

### Example 1: Register Common Tools

```bash
# Register filesystem tool
curl -X POST 'http://localhost:8765/tools?name=tool-filesystem&source=builtin&module=tool-filesystem&description=Filesystem operations tool'

# Register bash tool
curl -X POST 'http://localhost:8765/tools?name=tool-bash&source=builtin&module=tool-bash&description=Execute bash commands'

# Register web tool
curl -X POST 'http://localhost:8765/tools?name=tool-web&source=git+https://github.com/microsoft/amplifier-tool-web@main&module=tool-web&description=Web scraping and HTTP requests'

# List all registered tools
curl 'http://localhost:8765/tools?from_registry=true'
```

### Example 2: Register LLM Providers

```bash
# Register Anthropic provider (production)
curl -X POST 'http://localhost:8765/providers?name=anthropic-prod&module=provider-anthropic&source=git+https://github.com/microsoft/amplifier-module-provider-anthropic@main&description=Production Anthropic provider' \
  -H "Content-Type: application/json" \
  -d '{"default_model": "claude-sonnet-4-5-20250929", "priority": 1}'

# Register OpenAI provider (development)
curl -X POST 'http://localhost:8765/providers?name=openai-dev&module=provider-openai&description=Development OpenAI provider' \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4", "priority": 2}'

# Register Azure provider
curl -X POST 'http://localhost:8765/providers?name=azure&module=provider-azure&description=Azure OpenAI provider' \
  -H "Content-Type: application/json" \
  -d '{"deployment_name": "gpt-4", "api_version": "2024-02-01"}'

# List all registered providers
curl http://localhost:8765/providers
```

### Example 3: Build Config from Registry

```bash
#!/bin/bash

# 1. List available tools and providers
echo "=== Available Tools ==="
curl -s 'http://localhost:8765/tools?from_registry=true' | jq '.tools[] | .name'

echo "=== Available Providers ==="
curl -s http://localhost:8765/providers | jq 'keys[]'

# 2. Create a complete config using registered components
CONFIG_ID=$(curl -s -X POST http://localhost:8765/configs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "registry-demo",
    "description": "Config built from registry components",
    "yaml_content": "bundle:\n  name: registry-demo\n  version: 1.0.0\n\nincludes:\n  - bundle: git+https://github.com/microsoft/amplifier-foundation@main\n\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: ${ANTHROPIC_API_KEY}\n      default_model: claude-sonnet-4-5-20250929\n\ntools:\n  - module: tool-filesystem\n  - module: tool-bash\n  - module: tool-web\n    source: git+https://example.com/tool-web\n\nsession:\n  orchestrator: loop-basic\n  context: context-simple\n"
  }' | jq -r '.config_id')

echo "Created config: $CONFIG_ID"

# 3. View the config
echo "=== Final Config ==="
curl -s "http://localhost:8765/configs/$CONFIG_ID" | jq '.yaml_content'
```

### Example 4: Registry Management UI

```javascript
// Frontend code for managing registries

class RegistryManager {
  async listTools() {
    const response = await fetch('/tools?from_registry=true');
    return await response.json();
  }

  async registerTool(name, source, options = {}) {
    const params = new URLSearchParams({
      name,
      source,
      ...options
    });

    const response = await fetch(`/tools?${params}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options.config || {})
    });

    return await response.json();
  }

  async listProviders() {
    const response = await fetch('/providers');
    return await response.json();
  }

  async registerProvider(name, module, options = {}) {
    const params = new URLSearchParams({
      name,
      module,
      ...options
    });

    const response = await fetch(`/providers?${params}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options.config || {})
    });

    return await response.json();
  }

  async buildConfigFromRegistry(configName, toolNames, providerName) {
    // Build YAML content with all components
    const toolsList = toolNames.map(t => `  - module: ${t}`).join('\n');
    const yamlContent = `bundle:
  name: ${configName}
  version: 1.0.0

includes:
  - bundle: foundation

providers:
  - module: ${providerName}
    config:
      api_key: \${API_KEY}

tools:
${toolsList}

session:
  orchestrator: loop-basic
  context: context-simple
`;

    // Create complete config
    const response = await fetch('/configs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: configName,
        yaml_content: yamlContent
      })
    });

    const config = await response.json();
    return config.config_id;
  }
}

// Usage
const registry = new RegistryManager();

// Register components
await registry.registerTool('tool-custom', 'git+https://example.com/tool-custom');
await registry.registerProvider('anthropic', 'provider-anthropic', {
  config: { default_model: 'claude-sonnet-4-5-20250929' }
});

// Build config from registry
const configId = await registry.buildConfigFromRegistry(
  'my-config',
  ['tool-filesystem', 'tool-bash', 'tool-custom'],
  'anthropic'
);
```

---

## Summary

### Endpoint Overview

| Category | Endpoint | Method | Description |
|----------|----------|--------|-------------|
| **Tools** | `/tools` | POST | Register tool |
| | `/tools?from_registry=true` | GET | List tools |
| | `/tools/{name}?from_registry=true` | GET | Get tool |
| | `/tools/{name}` | DELETE | Remove tool |
| **Providers** | `/providers` | POST | Register provider |
| | `/providers` | GET | List providers |
| | `/providers/{name}` | GET | Get provider |
| | `/providers/{name}` | DELETE | Remove provider |
| **Bundles** | `/bundles` | POST | Register bundle |
| | `/bundles` | GET | List bundles |
| | `/bundles/{name}` | GET | Get bundle |
| | `/bundles/{name}` | DELETE | Remove bundle |

### Key Benefits

✅ **Discovery** - Centralized catalog of available components
✅ **Reuse** - Register once, use in multiple configs
✅ **Consistency** - Standardized components across the platform
✅ **Management** - Easy to add, list, and remove components

---

## Related Documentation

- [Config API](./CONFIG_API.md) - Creating and managing configs
- [Bundle API](./BUNDLE_API.md) - Bundle-specific operations
- [Session API](./SESSION_API.md) - Using configs to create sessions
- [Database Schema](./POSTGRESQL_MIGRATION_SUMMARY.md) - Storage details
