# Architecture Changes - Config & Session Refactor

## Overview

We've refactored the system to use two core primitives: **Configs** and **Sessions**.

### Before
- Sessions contained everything: bundle name, provider details, model, config, metadata
- ConfigManager handled providers, bundles, modules separately
- Complex session creation with many parameters

### After
- **Config**: Complete YAML bundle (the "what")
- **Session**: Runtime instance referencing a Config (the "instance")
- Clean separation of concerns

---

## 1. Config Model

```python
class Config(BaseModel):
    config_id: str              # UUID
    name: str                   # Human-readable name
    description: str | None     # Optional description
    yaml_content: str           # Complete YAML bundle as string
    created_at: datetime
    updated_at: datetime
    tags: dict[str, str]        # Metadata for categorization
```

**Key Points:**
- Stores the **complete YAML bundle** including:
  - Bundle metadata
  - Tools, hooks, providers
  - Session configuration (orchestrator, context manager)
  - Agents, spawn policies
  - All includes
- Configs are reusable - multiple sessions can use the same config

---

## 2. Simplified Session Model

```python
class Session(BaseModel):
    session_id: str             # UUID
    config_id: str              # References a Config
    status: SessionStatus       # active, completed, failed, cancelled
    metadata: SessionMetadata   # config_id, timestamps, message_count
    transcript: list[dict]      # Conversation history
```

**Key Points:**
- Session is just a **runtime instance**
- References config via `config_id`
- No duplicate storage of bundle/provider/model info
- Clean separation: Config = definition, Session = execution

---

## 3. Database Schema

### New `configs` Table
```sql
CREATE TABLE configs (
    config_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    yaml_content TEXT NOT NULL,    -- Complete YAML bundle
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    tags TEXT                       -- JSON
);
```

### Simplified `sessions` Table
```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    config_id TEXT NOT NULL,        -- Foreign key to configs
    status TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    message_count INTEGER DEFAULT 0,
    transcript TEXT,                -- JSON array
    FOREIGN KEY (config_id) REFERENCES configs(config_id)
);
```

**Removed from sessions:**
- bundle, provider, model (now in config)
- metadata, config fields (redundant)

---

## 4. ConfigManager

New manager for complete CRUD operations on configs:

```python
class ConfigManager:
    # Core CRUD
    async def create_config(name, yaml_content, description, tags) -> Config
    async def get_config(config_id) -> Config | None
    async def update_config(config_id, ...) -> Config | None
    async def delete_config(config_id) -> bool
    async def list_configs(limit, offset) -> tuple[list[ConfigMetadata], int]
    
    # Helper methods for programmatic manipulation
    async def add_tool_to_config(config_id, module, source, config)
    async def add_provider_to_config(config_id, module, source, config)
    async def merge_bundle_into_config(config_id, bundle_uri)
    
    # YAML utilities
    def parse_yaml(yaml_content) -> dict
    def dump_yaml(data) -> str
```

**Key Features:**
- Validates YAML syntax on create/update
- Helper methods to programmatically add tools/providers/bundles
- YAML parsing/dumping utilities

---

## 5. SessionManager Changes

Completely rewritten to work with `config_id`:

```python
class SessionManager:
    async def create_session(config_id: str) -> Session
    async def resume_session(session_id: str) -> Session | None
    async def send_message(session_id, message) -> dict
    async def stream_message(session_id, message)
    async def get_session(session_id) -> Session | None
    async def list_sessions(limit, offset) -> list[Session]
    async def delete_session(session_id) -> bool
```

**How it works:**
1. User creates a session with a `config_id`
2. SessionManager loads the Config from database
3. Writes YAML to temporary file
4. Loads via BundleRegistry (resolves all includes, loads modules)
5. Prepares bundle (creates mount plan)
6. Creates AmplifierSession from prepared bundle
7. Caches prepared bundle by `config_id` for reuse

**Key Changes:**
- No more `bundle`, `provider`, `model` parameters
- Single source of truth: the Config's YAML
- Automatic bundle preparation from YAML
- Caching of prepared bundles

---

## 6. Config API Endpoints

New REST API for configs:

### Core CRUD
- `POST /configs` - Create new config
- `GET /configs` - List all configs (with pagination)
- `GET /configs/{config_id}` - Get config by ID
- `PUT /configs/{config_id}` - Update config
- `DELETE /configs/{config_id}` - Delete config

### Helper Endpoints
- `POST /configs/{config_id}/tools` - Add tool to config
- `POST /configs/{config_id}/providers` - Add provider to config
- `POST /configs/{config_id}/bundles` - Merge bundle into config

**Example: Create Config**
```bash
POST /configs
{
  "name": "my-dev-config",
  "description": "Development configuration with Anthropic",
  "yaml_content": "
bundle:
  name: my-config
  version: 1.0.0

includes:
  - bundle: foundation

providers:
  - module: provider-anthropic
    config:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-5

session:
  orchestrator: loop-streaming
  context: context-persistent
"
}
```

---

## 7. The New Flow

### Creating and Using a Session

```
1. User creates Config (YAML bundle)
   POST /configs
   {
     "name": "my-config",
     "yaml_content": "..."
   }
   → Returns config_id

2. User creates Session from Config
   POST /sessions
   {
     "config_id": "abc-123-def"
   }
   → Returns session_id
   
   Behind the scenes:
   - SessionManager loads Config YAML
   - Creates temp file with YAML
   - BundleRegistry loads and resolves includes
   - Prepares bundle (mount plan)
   - Creates AmplifierSession
   - Caches prepared bundle

3. User sends messages to Session
   POST /sessions/{session_id}/messages
   {
     "message": "Hello!"
   }
   → Uses the prepared bundle from step 2
```

### Benefits

1. **Reusability**: Create one config, use for multiple sessions
2. **Versioning**: Track config changes over time
3. **Sharing**: Export/import configs as YAML
4. **Simplicity**: Sessions are just runtime instances
5. **Single Source of Truth**: Config YAML defines everything

---

## 8. Migration Path

### Old Way (Before)
```python
# Create session with everything inline
session = await session_manager.create_session(
    bundle="foundation",
    provider="anthropic",
    model="claude-sonnet-4-5",
    config={...},
    metadata={...}
)
```

### New Way (After)
```python
# 1. Create config once
config = await config_manager.create_config(
    name="my-config",
    yaml_content="""
bundle:
  name: my-config
includes:
  - bundle: foundation
providers:
  - module: provider-anthropic
    config:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-5
"""
)

# 2. Create sessions from config (can reuse)
session = await session_manager.create_session(
    config_id=config.config_id
)
```

---

## 9. What's Next

### Completed ✅
- Config data model
- ConfigManager with CRUD operations
- Database schema updates
- Simplified Session model
- SessionManager refactor
- Config API endpoints

### In Progress 🚧
- Session API endpoint updates

### To Do ☐
- Update all tests
- Update documentation
- Migration guide for existing data

---

## 10. API Changes Summary

### New Endpoints
- `/configs` - Complete CRUD for configs
- `/configs/{id}/tools` - Add tool helper
- `/configs/{id}/providers` - Add provider helper
- `/configs/{id}/bundles` - Merge bundle helper

### Changed Endpoints
- `POST /sessions` - Now requires `config_id` instead of bundle/provider/model

### Removed Endpoints
- Old provider/bundle management endpoints (replaced by configs)

---

## 11. Example: Complete Workflow

```bash
# 1. Create a config
curl -X POST http://localhost:8000/configs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "development",
    "description": "Dev config with Anthropic",
    "yaml_content": "bundle:\n  name: dev-config\nincludes:\n  - bundle: foundation\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: sk-ant-...\n      model: claude-sonnet-4-5"
  }'

# Response: { "config_id": "abc-123", ... }

# 2. Create a session from the config
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "config_id": "abc-123"
  }'

# Response: { "session_id": "xyz-789", ... }

# 3. Send a message
curl -X POST http://localhost:8000/sessions/xyz-789/messages \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, how are you?"
  }'

# 4. Create another session from same config (reuse!)
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "config_id": "abc-123"
  }'
```

---

## Summary

This refactor achieves:
- **Clarity**: Two primitives (Config, Session) instead of many
- **Reusability**: Configs can be shared across sessions
- **Simplicity**: Sessions are lightweight runtime instances
- **Flexibility**: Programmatic config manipulation via helpers
- **Correctness**: Single source of truth (Config YAML)

The flow is now: **Settings → Config → Mount Plan → Session**
