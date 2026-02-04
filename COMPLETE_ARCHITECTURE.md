# Complete Config & Session Architecture

## ✅ Final Implementation

### Two Core Primitives

**1. Config (The "What")**
- Complete YAML bundle stored as string
- Includes all components: tools, providers, session config, agents, etc.
- Reusable across multiple sessions
- Full CRUD operations

**2. Session (The "Instance")**
- References a Config via `config_id`
- Lightweight runtime state
- Transcript storage
- Status tracking

---

## The Complete Flow

```
┌──────────────────────────────────────────────────────────────┐
│ 1. User creates Config with YAML bundle                     │
│    POST /configs                                             │
│    {                                                         │
│      "name": "my-dev-config",                               │
│      "yaml_content": "bundle:\n  name: dev\n..."           │
│    }                                                         │
│    → Returns config_id                                      │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ 2. Config stored in database                                │
│    configs table:                                           │
│    - config_id: UUID                                        │
│    - name: "my-dev-config"                                  │
│    - yaml_content: "bundle:..."  ← Complete YAML            │
│    - created_at, updated_at, tags                           │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ 3. User creates Session from Config                         │
│    POST /sessions                                            │
│    {                                                         │
│      "config_id": "abc-123-def-456"                         │
│    }                                                         │
│    → Returns session_id                                     │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ 4. SessionManager prepares bundle                           │
│    a. Load config from database                             │
│    b. Parse YAML string to dict: yaml.safe_load()           │
│    c. Extract markdown body (if present after ---)          │
│    d. Bundle.from_dict(config_dict, base_path=cwd)          │
│    e. Set bundle.instruction = markdown_body                │
│    f. prepared = await bundle.prepare(install_deps=True)    │
│    g. Cache prepared bundle by config_id                    │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ 5. Create AmplifierSession                                  │
│    session = await prepared.create_session(                │
│        session_id=UUID,                                     │
│        session_cwd=Path.cwd(),                              │
│        is_resumed=False                                     │
│    )                                                        │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ 6. Session stored in database                               │
│    sessions table:                                          │
│    - session_id: UUID                                       │
│    - config_id: → references configs table                  │
│    - status: "active"                                       │
│    - transcript: []                                         │
│    - message_count: 0                                       │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ 7. User sends messages                                      │
│    POST /sessions/{session_id}/messages                     │
│    {                                                         │
│      "message": "Hello!"                                    │
│    }                                                         │
│    → Uses cached prepared bundle from step 4                │
│    → Executes via AmplifierSession                          │
│    → Updates transcript                                     │
└──────────────────────────────────────────────────────────────┘
```

---

## Key Implementation Details

### 1. No Temp Files! ✅

**Old approach (removed):**
```python
# ❌ Write YAML to temp file
with tempfile.NamedTemporaryFile(...) as f:
    f.write(config.yaml_content)
    bundle = registry._load_single(f.name)
```

**New approach:**
```python
# ✅ Create Bundle directly from dict
config_dict = yaml.safe_load(config.yaml_content)
bundle = Bundle.from_dict(config_dict, base_path=Path.cwd())
prepared = await bundle.prepare(install_deps=True)
```

### 2. Markdown Body Support ✅

Configs can be either:

**Pure YAML:**
```yaml
bundle:
  name: my-config
includes:
  - bundle: foundation
providers:
  - module: provider-anthropic
    config:
      api_key: ${ANTHROPIC_API_KEY}
```

**YAML Frontmatter + Markdown Body:**
```yaml
---
bundle:
  name: my-config
includes:
  - bundle: foundation
---

# My Config Instructions

You are a helpful assistant with access to...

## Usage

@my-config:context/instructions.md
```

The code detects the `---` separator and extracts the markdown body as `bundle.instruction`.

### 3. Bundle Caching ✅

```python
self._prepared_bundles[config_id] = prepared
```

**Benefits:**
- Same config → same prepared bundle → instant reuse
- No repeated bundle preparation
- Multiple sessions from same config are cheap

---

## API Reference

### Config Endpoints

```bash
# Create config
POST /configs
{
  "name": "my-dev-config",
  "description": "Development configuration",
  "yaml_content": "bundle:\n  name: dev\n...",
  "tags": {"env": "dev", "version": "1.0"}
}
→ Returns: ConfigResponse with config_id

# List configs (paginated)
GET /configs?limit=10&offset=0
→ Returns: ConfigListResponse

# Get specific config
GET /configs/{config_id}
→ Returns: ConfigResponse with full YAML

# Update config
PUT /configs/{config_id}
{
  "name": "updated-name",
  "yaml_content": "...",
  "description": "...",
  "tags": {...}
}
→ Returns: ConfigResponse

# Delete config
DELETE /configs/{config_id}
→ Returns: {"message": "Config deleted successfully"}

# Helpers
POST /configs/{config_id}/tools?tool_module=tool-web&tool_source=...&tool_config={...}
POST /configs/{config_id}/providers?provider_module=provider-anthropic&provider_config={...}
POST /configs/{config_id}/bundles?bundle_uri=foundation
```

### Session Endpoints

```bash
# Create session from config
POST /sessions
{
  "config_id": "abc-123-def-456"
}
→ Returns: SessionResponse with session_id

# List sessions (paginated)
GET /sessions?limit=10&offset=0
→ Returns: SessionListResponse

# Get session details
GET /sessions/{session_id}
→ Returns: SessionResponse

# Resume session (load into memory)
POST /sessions/{session_id}/resume
→ Returns: SessionResponse

# Send message
POST /sessions/{session_id}/messages
{
  "message": "Hello!",
  "context": {}
}
→ Returns: MessageResponse with response text

# Stream message (SSE)
POST /sessions/{session_id}/stream
{
  "message": "Hello!"
}
→ Returns: Server-Sent Events stream

# Delete session
DELETE /sessions/{session_id}
→ Returns: {"message": "Session deleted successfully"}

# Cancel current operation
POST /sessions/{session_id}/cancel
→ Returns: {"message": "Cancellation requested"}
```

---

## Data Models

### Config
```python
class Config(BaseModel):
    config_id: str              # UUID
    name: str                   # Human-readable
    description: str | None     # Optional
    yaml_content: str           # Complete YAML bundle
    created_at: datetime
    updated_at: datetime
    tags: dict[str, str]        # Metadata
```

### ConfigMetadata (for listings)
```python
class ConfigMetadata(BaseModel):
    config_id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    tags: dict[str, str]
    # Note: No yaml_content (saves tokens/bandwidth)
```

### Session
```python
class Session(BaseModel):
    session_id: str             # UUID
    config_id: str              # References Config
    status: SessionStatus       # active/completed/failed/cancelled
    metadata: SessionMetadata   # config_id, timestamps, message_count
    transcript: list[dict]      # Conversation history
```

### SessionMetadata
```python
class SessionMetadata(BaseModel):
    config_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    tags: dict[str, str]
```

---

## Database Schema

```sql
-- Configs table (complete YAML bundles)
CREATE TABLE configs (
    config_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    yaml_content TEXT NOT NULL,        -- Complete YAML
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    tags TEXT                          -- JSON
);

-- Sessions table (runtime instances)
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    config_id TEXT NOT NULL,           -- Foreign key
    status TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    message_count INTEGER DEFAULT 0,
    transcript TEXT,                   -- JSON array
    FOREIGN KEY (config_id) REFERENCES configs(config_id)
);

-- Indexes
CREATE INDEX idx_configs_name ON configs(name);
CREATE INDEX idx_configs_created_at ON configs(created_at);
CREATE INDEX idx_sessions_config_id ON sessions(config_id);
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_created_at ON sessions(created_at);
```

---

## Example: Complete Workflow

### 1. Create a Config

```bash
curl -X POST http://localhost:8000/configs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "development",
    "description": "Development configuration with Anthropic",
    "yaml_content": "---\nbundle:\n  name: dev-config\n  version: 1.0.0\n\nincludes:\n  - bundle: foundation\n\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: ${ANTHROPIC_API_KEY}\n      model: claude-sonnet-4-5\n      max_tokens: 4096\n\nsession:\n  orchestrator: loop-streaming\n  context: context-persistent\n\ntools:\n  - module: tool-filesystem\n    config:\n      allowed_paths: [.]\n  - module: tool-bash\n  - module: tool-web\n\n---\n\n# Development Assistant\n\nYou are a helpful development assistant.\n",
    "tags": {
      "env": "development",
      "provider": "anthropic"
    }
  }'
```

**Response:**
```json
{
  "config_id": "c7a3f9e2-1b4d-4c8a-9f2e-d6b8a1c5e3f7",
  "name": "development",
  "description": "Development configuration with Anthropic",
  "yaml_content": "...",
  "created_at": "2026-02-04T16:00:00Z",
  "updated_at": "2026-02-04T16:00:00Z",
  "tags": {"env": "development", "provider": "anthropic"},
  "message": "Config created successfully"
}
```

### 2. Create a Session from the Config

```bash
curl -X POST http://localhost:8000/sessions \
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

**What happens behind the scenes:**
1. SessionManager loads Config from database
2. Parses YAML: `config_dict = yaml.safe_load(yaml_content)`
3. Extracts markdown body (if present after `---`)
4. Creates Bundle: `Bundle.from_dict(config_dict, base_path=Path.cwd())`
5. Sets instruction: `bundle.instruction = markdown_body`
6. Prepares bundle: `prepared = await bundle.prepare(install_deps=True)`
7. Creates AmplifierSession: `await prepared.create_session(...)`
8. Caches prepared bundle by `config_id`
9. Stores session in database

### 3. Send Messages

```bash
curl -X POST http://localhost:8000/sessions/s1a2b3c4-5d6e-7f8g-9h0i-1j2k3l4m5n6o/messages \
  -H "Content-Type: application/json" \
  -d '{
    "message": "List files in the current directory"
  }'
```

**Response:**
```json
{
  "session_id": "s1a2b3c4-5d6e-7f8g-9h0i-1j2k3l4m5n6o",
  "response": "Here are the files in the current directory: ...",
  "metadata": {
    "config_id": "c7a3f9e2-1b4d-4c8a-9f2e-d6b8a1c5e3f7"
  }
}
```

### 4. Reuse the Config (Multiple Sessions)

```bash
# Create another session from the SAME config
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "config_id": "c7a3f9e2-1b4d-4c8a-9f2e-d6b8a1c5e3f7"
  }'
```

**Benefits:**
- Bundle already prepared and cached ✅
- Instant session creation ✅
- Same configuration guaranteed ✅

---

## ConfigManager API

### Core CRUD Operations

```python
class ConfigManager:
    async def create_config(
        name: str,
        yaml_content: str,
        description: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> Config:
        """Create new config with YAML validation."""
        
    async def get_config(config_id: str) -> Config | None:
        """Get config by ID."""
        
    async def update_config(
        config_id: str,
        name: str | None = None,
        yaml_content: str | None = None,
        description: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> Config | None:
        """Update config (validates YAML if provided)."""
        
    async def delete_config(config_id: str) -> bool:
        """Delete config."""
        
    async def list_configs(
        limit: int = 50,
        offset: int = 0
    ) -> tuple[list[ConfigMetadata], int]:
        """List configs with pagination."""
```

### Helper Methods (Programmatic YAML Manipulation)

```python
    def parse_yaml(yaml_content: str) -> dict[str, Any]:
        """Parse YAML string to dict."""
        
    def dump_yaml(data: dict[str, Any]) -> str:
        """Dump dict to YAML string."""
        
    async def add_tool_to_config(
        config_id: str,
        module: str,
        source: str,
        config: dict[str, Any] | None = None,
    ) -> Config | None:
        """Add tool to config's YAML."""
        
    async def add_provider_to_config(
        config_id: str,
        module: str,
        source: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> Config | None:
        """Add provider to config's YAML."""
        
    async def merge_bundle_into_config(
        config_id: str,
        bundle_uri: str
    ) -> Config | None:
        """Add bundle to includes section."""
```

---

## SessionManager API

### Simplified Session Operations

```python
class SessionManager:
    async def create_session(config_id: str) -> Session:
        """Create session from config (loads YAML, prepares bundle)."""
        
    async def get_session(session_id: str) -> Session | None:
        """Get session by ID."""
        
    async def list_sessions(
        limit: int = 50,
        offset: int = 0
    ) -> list[Session]:
        """List sessions with pagination."""
        
    async def resume_session(session_id: str) -> Session | None:
        """Resume session (loads into memory if needed)."""
        
    async def delete_session(session_id: str) -> bool:
        """Delete session and cleanup."""
        
    async def send_message(
        session_id: str,
        message: str,
        context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send message and get response."""
        
    async def stream_message(
        session_id: str,
        message: str,
        context: dict[str, Any] | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream message with SSE events."""
```

---

## Example Config YAMLs

### Minimal Development Config

```yaml
bundle:
  name: minimal-dev
  version: 1.0.0

includes:
  - bundle: foundation

providers:
  - module: provider-anthropic
    config:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-5

session:
  orchestrator: loop-basic
  context: context-simple
```

### Full Production Config

```yaml
---
bundle:
  name: production
  version: 1.0.0
  description: Production configuration

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main

providers:
  - module: provider-anthropic
    source: git+https://github.com/microsoft/amplifier-module-provider-anthropic@main
    config:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-5
      max_tokens: 4096
      temperature: 0.7

session:
  orchestrator: loop-streaming
  context: context-persistent
  injection_budget_per_turn: 500
  injection_size_limit: 8192

context:
  config:
    max_tokens: 128000
    compact_threshold: 0.85
    auto_compact: true

tools:
  - module: tool-filesystem
    source: git+https://github.com/microsoft/amplifier-module-tool-filesystem@main
    config:
      allowed_paths: ["/app/data"]
      allowed_write_paths: ["/app/data/output"]
      require_approval: true
  
  - module: tool-bash
    source: git+https://github.com/microsoft/amplifier-module-tool-bash@main
    config:
      blocked_commands: ["rm -rf", "sudo"]
      timeout_seconds: 30
      require_approval: true
  
  - module: tool-web
  - module: tool-search
    config:
      provider: brave
      api_key: ${BRAVE_API_KEY}

hooks:
  - module: hooks-logging
    config:
      output_dir: /var/log/amplifier
      log_level: INFO
  
  - module: hooks-approval
    config:
      require_approval_for:
        - tool-filesystem:write_file
        - tool-bash:execute
  
  - module: hooks-cost-tracking
    config:
      alert_threshold: 10.0
      hard_limit: 50.0

spawn:
  exclude_tools:
    - tool-task

---

# Production Assistant

You are a production-grade AI assistant with restricted capabilities.

## Security

- All file writes require approval
- All bash commands require approval
- Cost tracking enforced

## Available Capabilities

@production:context/capabilities.md
```

### Multi-Provider Config

```yaml
bundle:
  name: multi-provider
  version: 1.0.0

includes:
  - bundle: foundation

providers:
  - module: provider-anthropic
    config:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-5
  
  - module: provider-openai
    config:
      api_key: ${OPENAI_API_KEY}
      model: gpt-4o
  
  - module: provider-ollama
    config:
      model: llama3
      base_url: http://localhost:11434

session:
  orchestrator: loop-streaming
  context: context-simple
```

---

## Code Structure

```
amplifier_app_api/
├── models/
│   ├── config.py           ← Config, ConfigMetadata, Config*Request/Response
│   ├── session.py          ← Session, SessionMetadata, SessionStatus (simplified)
│   ├── requests.py         ← SessionCreateRequest (simplified)
│   └── responses.py        ← SessionInfo, SessionResponse (simplified)
│
├── core/
│   ├── config_manager.py   ← Config CRUD + helpers
│   └── session_manager.py  ← Session management + Bundle.from_dict()
│
├── storage/
│   └── database.py         ← New schema with configs + sessions tables
│
└── api/
    ├── config.py           ← Config REST API
    └── sessions.py         ← Session REST API (updated)
```

---

## Validation ✅

### YAML Logic Test
```bash
python3 test_config_logic.py
```

**Results:**
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

### Code Quality
```
✓ All files pass python_check
✓ No type errors (pyright)
✓ No lint errors (ruff)
✓ No formatting issues
✓ No stub/placeholder code
```

---

## Benefits of This Architecture

### 1. Single Source of Truth
- Config YAML defines everything
- No duplication between session and config
- Changes to config affect all future sessions

### 2. Reusability
- One config → unlimited sessions
- Bundle preparation cached
- Fast session creation

### 3. Simplicity
- Two primitives: Config, Session
- Clear separation: definition vs instance
- Minimal session state

### 4. Flexibility
- Programmatic YAML manipulation
- Helper methods for common operations
- Direct YAML editing for advanced users

### 5. Type Safety
- Pydantic validation
- YAML syntax validation
- Clear error messages

### 6. No Temp Files
- Direct dict-to-Bundle conversion
- Cleaner, more efficient
- Follows amplifier-foundation patterns

---

## Migration Notes

### From Old Architecture

**Old session creation:**
```python
session = await manager.create_session(
    bundle="foundation",
    provider="anthropic", 
    model="claude-sonnet-4-5",
    config={...},
    metadata={...}
)
```

**New session creation:**
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

# 2. Create sessions from config (reusable)
session = await session_manager.create_session(
    config_id=config.config_id
)
```

---

## Files Changed Summary

### New Files
- ✅ `amplifier_app_api/models/config.py` - Config models
- ✅ `tests/test_new_architecture.py` - Comprehensive tests
- ✅ `test_config_logic.py` - Standalone validation
- ✅ `ARCHITECTURE_CHANGES.md` - Architecture docs
- ✅ `REFACTOR_REVIEW.md` - Review docs
- ✅ `COMPLETE_ARCHITECTURE.md` - This document

### Modified Files
- ✅ `amplifier_app_api/core/config_manager.py` - Complete rewrite
- ✅ `amplifier_app_api/core/session_manager.py` - Bundle.from_dict() approach
- ✅ `amplifier_app_api/storage/database.py` - New schema + methods
- ✅ `amplifier_app_api/models/session.py` - Simplified
- ✅ `amplifier_app_api/models/requests.py` - Updated SessionCreateRequest
- ✅ `amplifier_app_api/models/responses.py` - Updated SessionInfo/SessionResponse
- ✅ `amplifier_app_api/api/config.py` - New Config API
- ✅ `amplifier_app_api/api/sessions.py` - Updated to use config_id
- ✅ `amplifier_app_api/models/__init__.py` - Export Config models

---

## Summary

**Architecture complete:** Two-primitive system (Config + Session) with clean separation between configuration and runtime.

**No temp files:** Direct `Bundle.from_dict()` conversion following amplifier-foundation patterns.

**Full CRUD:** Complete lifecycle management for configs with programmatic helpers.

**Validated:** YAML logic tested, code quality verified, type-safe throughout.

**Ready for:** Integration testing with actual amplifier-core/foundation imports.
