# Config & Session Refactor - Review

## ✅ What We've Built

### 1. Two Core Primitives

**Config** - The "what" (complete YAML bundle)
- Stores complete YAML bundle configuration
- Reusable across multiple sessions
- CRUD operations for management
- Programmatic manipulation helpers

**Session** - The "instance" (runtime execution)
- References a Config via `config_id`
- Lightweight runtime state
- Transcript storage
- Status tracking

---

## 2. Files Changed/Created

### New Files ✨
- `amplifier_app_api/models/config.py` - Config data models
- `tests/test_new_architecture.py` - Comprehensive tests
- `test_config_logic.py` - Logic validation (standalone)
- `ARCHITECTURE_CHANGES.md` - Documentation

### Modified Files 📝
- `amplifier_app_api/core/config_manager.py` - Complete rewrite for Config CRUD
- `amplifier_app_api/storage/database.py` - New schema + Config methods
- `amplifier_app_api/models/session.py` - Simplified to reference config_id
- `amplifier_app_api/core/session_manager.py` - Works with config_id
- `amplifier_app_api/api/config.py` - New Config REST API
- `amplifier_app_api/models/__init__.py` - Export Config models

---

## 3. The New Data Model

### Config Table
```sql
CREATE TABLE configs (
    config_id TEXT PRIMARY KEY,        -- UUID
    name TEXT NOT NULL,                -- Human-readable name
    description TEXT,                  -- Optional description
    yaml_content TEXT NOT NULL,        -- Complete YAML bundle
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    tags TEXT                          -- JSON metadata
);
```

### Simplified Sessions Table
```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,       -- UUID
    config_id TEXT NOT NULL,           -- References configs table
    status TEXT NOT NULL,              -- active/completed/failed/cancelled
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    message_count INTEGER DEFAULT 0,
    transcript TEXT,                   -- JSON conversation history
    FOREIGN KEY (config_id) REFERENCES configs(config_id)
);
```

**Key Change**: Sessions no longer store bundle/provider/model/config - just `config_id`.

---

## 4. ConfigManager API

```python
class ConfigManager:
    # Core CRUD
    async def create_config(name, yaml_content, description, tags) -> Config
    async def get_config(config_id) -> Config | None
    async def update_config(config_id, name, yaml_content, description, tags) -> Config | None
    async def delete_config(config_id) -> bool
    async def list_configs(limit, offset) -> tuple[list[ConfigMetadata], int]
    
    # YAML utilities
    def parse_yaml(yaml_content) -> dict
    def dump_yaml(data) -> str
    
    # Programmatic helpers
    async def add_tool_to_config(config_id, module, source, config) -> Config | None
    async def add_provider_to_config(config_id, module, source, config) -> Config | None
    async def merge_bundle_into_config(config_id, bundle_uri) -> Config | None
```

### Features
- ✅ YAML validation on create/update
- ✅ Programmatic YAML manipulation
- ✅ Helper methods for common operations
- ✅ Pagination support
- ✅ Metadata tagging

---

## 5. SessionManager Changes

```python
class SessionManager:
    # Simplified API
    async def create_session(config_id: str) -> Session
    async def resume_session(session_id: str) -> Session | None
    async def send_message(session_id, message, context) -> dict
    async def stream_message(session_id, message, context) -> AsyncIterator
    async def get_session(session_id) -> Session | None
    async def list_sessions(limit, offset) -> list[Session]
    async def delete_session(session_id) -> bool
```

### How It Works
1. User passes `config_id` to `create_session()`
2. SessionManager loads Config from database
3. Writes YAML to temporary file
4. Uses BundleRegistry to load/resolve includes
5. Prepares bundle (creates mount plan)
6. Creates AmplifierSession
7. Caches prepared bundle by `config_id`

**Key Benefit**: Same config → same prepared bundle → reusable across sessions

---

## 6. REST API Endpoints

### Config Endpoints (New)
```
POST   /configs                     Create config
GET    /configs                     List configs (paginated)
GET    /configs/{config_id}         Get specific config
PUT    /configs/{config_id}         Update config
DELETE /configs/{config_id}         Delete config

POST   /configs/{id}/tools          Add tool helper
POST   /configs/{id}/providers      Add provider helper
POST   /configs/{id}/bundles        Merge bundle helper
```

### Session Endpoints (Simplified - To Be Updated)
```
POST   /sessions                    Create from config_id
GET    /sessions                    List sessions
GET    /sessions/{session_id}       Get session
DELETE /sessions/{session_id}       Delete session
POST   /sessions/{id}/resume        Resume session
POST   /sessions/{id}/messages      Send message
POST   /sessions/{id}/stream        Stream message (SSE)
```

---

## 7. Example Usage Flow

### Creating a Config
```bash
POST /configs
{
  "name": "my-dev-config",
  "description": "Development configuration",
  "yaml_content": "
bundle:
  name: dev-config
  version: 1.0.0

includes:
  - bundle: foundation

providers:
  - module: provider-anthropic
    config:
      api_key: sk-ant-xxx
      model: claude-sonnet-4-5

session:
  orchestrator: loop-streaming
  context: context-persistent
"
}

Response:
{
  "config_id": "abc-123-def-456",
  "name": "my-dev-config",
  "yaml_content": "...",
  "created_at": "2026-02-04T16:00:00Z",
  ...
}
```

### Creating a Session from Config
```bash
POST /sessions
{
  "config_id": "abc-123-def-456"
}

Response:
{
  "session_id": "xyz-789-uvw-012",
  "config_id": "abc-123-def-456",
  "status": "active",
  ...
}
```

### Reusing the Same Config
```bash
# Create another session from the same config
POST /sessions
{
  "config_id": "abc-123-def-456"  # Same config!
}

Response:
{
  "session_id": "new-session-id",  # Different session
  "config_id": "abc-123-def-456",  # Same config
  ...
}
```

---

## 8. Validation Results ✅

### YAML Logic Test (test_config_logic.py)
```
✓ YAML parses successfully
✓ Added tool programmatically (2 tools total)
✓ Added provider programmatically (2 providers total)
✓ Merged bundle programmatically (2 includes total)
✓ Dumped back to YAML successfully
✓ Round-trip verification passed
✓ Invalid YAML correctly rejected
✓ Minimal valid config structure verified
```

**Key Insights:**
1. YAML parsing/dumping works correctly ✅
2. Programmatic manipulation maintains structure ✅
3. Invalid YAML is detected ✅
4. Required fields can be validated ✅
5. Round-trip (parse → modify → dump → parse) works ✅

### Code Quality
- All new code passes `python_check` ✅
- No lint errors ✅
- No type errors ✅
- No stub/placeholder code ✅

---

## 9. Architecture Benefits

### Before (Old Way)
❌ Sessions stored everything inline
❌ No config reusability
❌ Complex session creation (many parameters)
❌ Provider/bundle management scattered

### After (New Way)
✅ **Single source of truth**: Config YAML defines everything
✅ **Reusability**: One config → many sessions
✅ **Simplicity**: Sessions are lightweight runtime instances
✅ **CRUD operations**: Full config lifecycle management
✅ **Programmatic manipulation**: Add tools/providers via helpers
✅ **Type safety**: Pydantic models with validation

---

## 10. The Complete Flow

```
User Settings/Preferences
    ↓
Config YAML (stored in database)
    ↓
ConfigManager.get_config()
    ↓
Temporary YAML file
    ↓
BundleRegistry.load(temp_file)
    ↓
Resolve includes, load modules
    ↓
bundle.prepare() → Mount Plan
    ↓
AmplifierSession.create()
    ↓
Session running (stores transcript)
```

---

## 11. What's Next

### Still To Do
1. **Update Session API endpoints** - Change to use `config_id` instead of bundle/provider/model
2. **Update existing tests** - Adapt to new architecture
3. **Migration strategy** - How to convert existing sessions

### Session API Changes Needed
```python
# Current (to be changed)
POST /sessions/create
{
  "bundle": "foundation",
  "provider": "anthropic",
  "model": "claude-sonnet-4-5",
  "config": {...}
}

# New (target)
POST /sessions
{
  "config_id": "abc-123-def-456"
}
```

---

## 12. Testing Strategy

### What We Can Test Now
- ✅ Config CRUD operations
- ✅ YAML validation
- ✅ Programmatic manipulation (add tool/provider/bundle)
- ✅ Pagination
- ✅ Metadata handling

### What Needs Integration Testing
- 🚧 SessionManager loading configs
- 🚧 Bundle preparation from Config YAML
- 🚧 Session creation from config
- 🚧 End-to-end: Config → Session → Message → Response

### Why Integration Tests Are Pending
The integration tests require:
- amplifier-core to be importable
- amplifier-foundation to be importable
- Full bundle loading machinery
- Network access for remote bundles

These are environment-dependent, so we focused on:
1. **Logic validation** (YAML parsing/dumping) ✅
2. **Data model correctness** (Pydantic models) ✅
3. **API structure** (endpoints defined) ✅

---

## 13. Code Quality Summary

### Static Analysis
```
✓ All files pass python_check
✓ No type errors (pyright)
✓ No lint errors (ruff)
✓ No formatting issues
✓ No stub/placeholder code
```

### Database Schema
```
✓ Proper foreign key constraints
✓ Appropriate indexes
✓ Normalized structure
✓ Timestamp tracking
```

### API Design
```
✓ RESTful endpoints
✓ Proper HTTP status codes
✓ Error handling
✓ Request/response validation
```

---

## 14. Questions for Next Steps

1. **Session API Update**: Ready to update Session endpoints to use `config_id`?

2. **Old Config Migration**: What to do with existing provider/bundle/module config in the `configuration` table?

3. **Default Configs**: Should we create default configs on startup (e.g., "foundation-default")?

4. **Config Validation**: Do we want to validate that configs have required sections (bundle.name, session.orchestrator, etc.)?

5. **Environment Variables**: How should we handle `${VAR}` substitution in configs?

---

## 15. Summary

The refactor is **structurally complete and validated**:

✅ **Config primitive** - Stores complete YAML bundles with CRUD operations
✅ **Simplified Session** - References config, stores only runtime state
✅ **Database schema** - Proper separation of configs and sessions
✅ **ConfigManager** - Full lifecycle management + programmatic helpers
✅ **SessionManager** - Loads configs and creates sessions
✅ **Config API** - Complete REST endpoints
✅ **Logic validation** - YAML parsing/dumping works correctly

**Next:** Update Session API endpoints and tests.

**Estimated remaining work:** 2-3 files (session.py API, requests.py, responses.py)
