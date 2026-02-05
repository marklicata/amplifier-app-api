# PostgreSQL Implementation Plan

## Overview

This document outlines the step-by-step implementation plan for migrating from SQLite to PostgreSQL. **No data migration needed** - fresh schema only.

## Prerequisites

✅ Azure PostgreSQL infrastructure provisioned  
☐ Implementation code changes  

---

## Implementation Phases

### Phase 1: Dependencies & Configuration (30 minutes)

**Tasks:**
1. Update dependencies (remove aiosqlite, add asyncpg)
2. Add environment-based configuration
3. Create Azure Key Vault integration (production)
4. Update .env files for each environment

**Files to modify:**
- `pyproject.toml`
- `amplifier_app_api/config.py`
- `.env.development` (create)
- `.env.test` (create)
- `.env.example` (update)
- `amplifier_app_api/utils/secrets.py` (create)

---

### Phase 2: Database Layer Refactor (2-3 hours)

**Tasks:**
1. Replace aiosqlite with asyncpg
2. Update connection management (connection pool)
3. Remove manual JSON serialization (asyncpg handles it)
4. Update parameter style (? → $1, $2, etc.)
5. Add PostgreSQL schema creation

**Files to modify:**
- `amplifier_app_api/storage/database.py` (major refactor)
- `amplifier_app_api/storage/schema.py` (create)
- `amplifier_app_api/storage/migrations.py` (update for PostgreSQL)

---

### Phase 3: Fix User-Session Relationship (1 hour)

**Tasks:**
1. Add user_id parameter to create_session()
2. Update session creation in SessionManager
3. Add session_participants table support
4. Add participant management operations

**Files to modify:**
- `amplifier_app_api/storage/database.py` (add user_id param)
- `amplifier_app_api/core/session_manager.py` (pass user_id)
- `amplifier_app_api/models/session_participant.py` (create)
- `amplifier_app_api/api/sessions.py` (add participant endpoints)

---

### Phase 4: Testing & Validation (1-2 hours)

**Tasks:**
1. Update test fixtures for asyncpg
2. Create local dev PostgreSQL setup (Docker Compose)
3. Test against local PostgreSQL
4. Test against Azure test database
5. Validate all CRUD operations

**Files to modify:**
- `tests/conftest.py`
- `tests/test_database.py`
- `docker-compose.dev.yml` (create)
- `scripts/init-dev-db.sql` (create)

---

## Detailed Implementation Steps

### Step 1: Update Dependencies

**File: `pyproject.toml`**

```toml
# Remove
# aiosqlite = "^0.19.0"

# Add
asyncpg = "^0.29.0"
azure-identity = "^1.15.0"  # For Key Vault
azure-keyvault-secrets = "^4.7.0"  # For Key Vault
```

**Run:**
```bash
uv sync
```

---

### Step 2: Create PostgreSQL Schema File

**File: `amplifier_app_api/storage/schema.py` (NEW)**

```python
"""PostgreSQL schema definitions."""

# Helper function for triggers
CREATE_UPDATED_AT_TRIGGER = """
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

# Configs table
CREATE_CONFIGS_TABLE = """
CREATE TABLE IF NOT EXISTS configs (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    yaml_content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tags JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_configs_name ON configs(name);
CREATE INDEX IF NOT EXISTS idx_configs_created_at ON configs(created_at);
CREATE INDEX IF NOT EXISTS idx_configs_tags ON configs USING GIN(tags);

DROP TRIGGER IF EXISTS update_configs_updated_at ON configs;
CREATE TRIGGER update_configs_updated_at
    BEFORE UPDATE ON configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
"""

# Applications table
CREATE_APPLICATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS applications (
    app_id VARCHAR(100) PRIMARY KEY,
    app_name VARCHAR(255) NOT NULL,
    api_key_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    settings JSONB DEFAULT '{}'::jsonb
);

DROP TRIGGER IF EXISTS update_applications_updated_at ON applications;
CREATE TRIGGER update_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
"""

# Users table
CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_app_id VARCHAR(100),
    total_sessions INTEGER NOT NULL DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb,
    
    CONSTRAINT users_total_sessions_check CHECK (total_sessions >= 0)
);

CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen);
CREATE INDEX IF NOT EXISTS idx_users_metadata ON users USING GIN(metadata);
"""

# Sessions table
CREATE_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_id UUID NOT NULL REFERENCES configs(config_id) ON DELETE CASCADE,
    owner_user_id UUID,
    created_by_app_id VARCHAR(100),
    last_accessed_by_app_id VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ,
    message_count INTEGER NOT NULL DEFAULT 0,
    transcript JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    
    CONSTRAINT sessions_status_check CHECK (status IN ('active', 'completed', 'failed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_sessions_config_id ON sessions(config_id);
CREATE INDEX IF NOT EXISTS idx_sessions_owner_user_id ON sessions(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_transcript ON sessions USING GIN(transcript);
CREATE INDEX IF NOT EXISTS idx_sessions_metadata ON sessions USING GIN(metadata);

DROP TRIGGER IF EXISTS update_sessions_updated_at ON sessions;
CREATE TRIGGER update_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
"""

# Session participants table (NEW)
CREATE_SESSION_PARTICIPANTS_TABLE = """
CREATE TABLE IF NOT EXISTS session_participants (
    session_id UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'viewer',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at TIMESTAMPTZ,
    permissions JSONB DEFAULT '{}'::jsonb,
    
    PRIMARY KEY (session_id, user_id),
    CONSTRAINT session_participants_role_check CHECK (role IN ('owner', 'editor', 'viewer'))
);

CREATE INDEX IF NOT EXISTS idx_session_participants_user_id ON session_participants(user_id);
CREATE INDEX IF NOT EXISTS idx_session_participants_session_id ON session_participants(session_id);
CREATE INDEX IF NOT EXISTS idx_session_participants_last_active ON session_participants(last_active_at);
"""

# Configuration table
CREATE_CONFIGURATION_TABLE = """
CREATE TABLE IF NOT EXISTS configuration (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL,
    scope VARCHAR(100) NOT NULL DEFAULT 'global',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_configuration_scope ON configuration(scope);

DROP TRIGGER IF EXISTS update_configuration_updated_at ON configuration;
CREATE TRIGGER update_configuration_updated_at
    BEFORE UPDATE ON configuration
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
"""

# Complete schema initialization
INIT_SCHEMA = f"""
{CREATE_UPDATED_AT_TRIGGER}
{CREATE_CONFIGS_TABLE}
{CREATE_APPLICATIONS_TABLE}
{CREATE_USERS_TABLE}
{CREATE_SESSIONS_TABLE}
{CREATE_SESSION_PARTICIPANTS_TABLE}
{CREATE_CONFIGURATION_TABLE}
"""
```

---

### Step 3: Refactor Database Class

**File: `amplifier_app_api/storage/database.py`**

Major changes needed:

1. **Replace connection with pool:**
```python
# OLD
self._connection: aiosqlite.Connection | None = None

# NEW
self._pool: asyncpg.Pool | None = None
```

2. **Update connect() method:**
```python
async def connect(self):
    """Connect to PostgreSQL and initialize schema."""
    if self._pool:
        return
    
    from .schema import INIT_SCHEMA
    
    # Create connection pool
    self._pool = await asyncpg.create_pool(
        self.db_url,
        min_size=settings.database_pool_min_size,
        max_size=settings.database_pool_max_size,
        command_timeout=60
    )
    
    # Initialize schema
    async with self._pool.acquire() as conn:
        await conn.execute(INIT_SCHEMA)
```

3. **Update all query methods to use $1, $2 parameter style:**
```python
# OLD (SQLite)
await conn.execute('INSERT INTO sessions (id, name) VALUES (?, ?)', (id, name))

# NEW (PostgreSQL)
await conn.execute('INSERT INTO sessions (id, name) VALUES ($1, $2)', id, name)
```

4. **Remove all json.dumps() and json.loads():**
```python
# OLD (SQLite requires manual JSON serialization)
transcript_json = json.dumps(transcript)
await conn.execute('UPDATE sessions SET transcript = ?', (transcript_json,))

# NEW (asyncpg handles automatically)
await conn.execute('UPDATE sessions SET transcript = $1', transcript)
```

5. **Update create_session to accept user_id:**
```python
async def create_session(
    self,
    session_id: str,  # Keep as string for now (UUID conversion later)
    config_id: str,
    owner_user_id: str | None,  # NEW parameter
    status: str,
    created_by_app_id: str | None = None,  # NEW parameter
):
    """Create a session with owner."""
    async with self._pool.acquire() as conn:
        async with conn.transaction():
            # Create session
            await conn.execute('''
                INSERT INTO sessions (
                    session_id, config_id, owner_user_id, 
                    created_by_app_id, status, message_count, transcript
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            ''', session_id, config_id, owner_user_id, created_by_app_id, status, 0, [])
            
            # Add owner as participant if user_id provided
            if owner_user_id:
                await conn.execute('''
                    INSERT INTO session_participants (session_id, user_id, role)
                    VALUES ($1, $2, $3)
                ''', session_id, owner_user_id, 'owner')
```

6. **Add session_participants operations:**
```python
async def add_session_participant(
    self,
    session_id: str,
    user_id: str,
    role: str = 'viewer'
):
    """Add a user to a session."""
    async with self._pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO session_participants (session_id, user_id, role)
            VALUES ($1, $2, $3)
            ON CONFLICT (session_id, user_id) DO UPDATE
            SET last_active_at = NOW()
        ''', session_id, user_id, role)

async def get_session_participants(self, session_id: str) -> list[dict]:
    """Get all participants for a session."""
    async with self._pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT user_id, role, joined_at, last_active_at, permissions
            FROM session_participants
            WHERE session_id = $1
            ORDER BY joined_at
        ''', session_id)
        return [dict(row) for row in rows]

async def get_user_sessions(self, user_id: str) -> list[dict]:
    """Get all sessions a user participates in."""
    async with self._pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT s.*, sp.role, sp.joined_at, sp.last_active_at
            FROM sessions s
            JOIN session_participants sp ON s.session_id = sp.session_id
            WHERE sp.user_id = $1
            ORDER BY sp.last_active_at DESC NULLS LAST
        ''', user_id)
        return [dict(row) for row in rows]
```

See full refactored file in next step.

---

### Step 4: Update SessionManager

**File: `amplifier_app_api/core/session_manager.py`**

Update session creation to pass user_id:

```python
async def create_session(
    self,
    config_id: str,
    user_id: str | None = None,  # NEW parameter
    app_id: str | None = None,   # NEW parameter
) -> Session:
    """Create a new session."""
    session_id = str(uuid.uuid4())
    
    # Create in database with user_id and app_id
    await self.db.create_session(
        session_id=session_id,
        config_id=config_id,
        owner_user_id=user_id,      # Pass user_id
        status="active",
        created_by_app_id=app_id,   # Pass app_id
    )
    
    # ... rest of method
```

**Update API endpoints to pass user_id from JWT:**

```python
# In api/sessions.py
@router.post("/", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    request_obj: Request,
    db: Database = Depends(get_db),
):
    """Create a new session."""
    # Get user_id from JWT (set by auth middleware)
    user_id = getattr(request_obj.state, 'user_id', None)
    app_id = getattr(request_obj.state, 'app_id', None)
    
    session = await session_manager.create_session(
        config_id=request.config_id,
        user_id=user_id,  # Pass from JWT
        app_id=app_id,    # Pass from API key
    )
    
    return SessionResponse(session=session)
```

---

### Step 5: Create SessionParticipant Model

**File: `amplifier_app_api/models/session_participant.py` (NEW)**

```python
"""Session participant model."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SessionParticipant(BaseModel):
    """Session participant with role-based access."""

    session_id: str = Field(..., description="Session ID")
    user_id: str = Field(..., description="User ID")
    role: str = Field(..., description="Role: owner, editor, viewer")
    joined_at: datetime = Field(..., description="When user joined session")
    last_active_at: datetime | None = Field(None, description="Last activity timestamp")
    permissions: dict[str, Any] = Field(default_factory=dict, description="Custom permissions")

    class Config:
        """Pydantic config."""
        from_attributes = True


class AddParticipantRequest(BaseModel):
    """Request to add participant to session."""

    user_id: str = Field(..., description="User ID to add")
    role: str = Field(default="viewer", description="Role: owner, editor, viewer")


class SessionParticipantResponse(BaseModel):
    """Response with session participants."""

    session_id: str
    participants: list[SessionParticipant]
```

---

### Step 6: Update Configuration

**File: `amplifier_app_api/config.py`**

Add environment-based configuration and Key Vault support:

```python
"""Application configuration using pydantic-settings."""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        # Load from .env.{ENVIRONMENT} first, then .env
        env_file=[
            f".env.{os.getenv('ENVIRONMENT', 'development')}",
            ".env",
        ],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: str = Field(
        default="development",
        description="Environment: development, test, staging, production",
    )

    # ... existing fields ...

    # Database - PostgreSQL
    database_url: str = Field(
        default="postgresql+asyncpg://amplifier_dev:dev_password@localhost:5432/amplifier_dev",
        description="Database connection URL",
    )
    database_pool_min_size: int = Field(
        default=10, description="Minimum database connection pool size"
    )
    database_pool_max_size: int = Field(
        default=20, description="Maximum database connection pool size"
    )

    # Azure Key Vault (production only)
    azure_keyvault_name: Optional[str] = Field(
        default=None, description="Azure Key Vault name for production secrets"
    )

    @field_validator("environment", mode="before")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment is one of allowed values."""
        allowed = {"development", "test", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v

    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    def is_development(self) -> bool:
        """Check if running in local development."""
        return self.environment == "development"

    # ... rest of Settings class ...
```

---

### Step 7: Create Key Vault Integration

**File: `amplifier_app_api/utils/secrets.py` (NEW)**

```python
"""Azure Key Vault integration for production secrets."""

import os
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


class SecretsManager:
    """Manage secrets from Azure Key Vault in production, env vars in dev."""

    def __init__(self):
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.vault_name = os.getenv("AZURE_KEYVAULT_NAME")
        self._client: Optional[SecretClient] = None

        if self.environment == "production" and self.vault_name:
            credential = DefaultAzureCredential()
            vault_url = f"https://{self.vault_name}.vault.azure.net"
            self._client = SecretClient(vault_url=vault_url, credential=credential)

    def get_secret(self, key: str, env_var_name: Optional[str] = None) -> Optional[str]:
        """
        Get secret from Key Vault (prod) or environment variable (dev/test).

        Args:
            key: Key Vault secret name
            env_var_name: Environment variable name (defaults to key.upper().replace('-', '_'))

        Returns:
            Secret value or None if not found
        """
        # Production: Load from Key Vault
        if self._client:
            try:
                secret = self._client.get_secret(key)
                return secret.value
            except Exception as e:
                # Log but don't crash - fallback to env var
                print(f"Warning: Failed to load {key} from Key Vault: {e}")

        # Dev/Test: Load from environment variable
        env_var = env_var_name or key.upper().replace("-", "_")
        return os.getenv(env_var)


# Global instance
secrets_manager = SecretsManager()
```

Update Settings class to use secrets_manager for production:

```python
from amplifier_app_api.utils.secrets import secrets_manager

class Settings(BaseSettings):
    # ... existing fields ...

    @property
    def database_url_resolved(self) -> str:
        """Get database URL, loading from Key Vault in production."""
        if self.is_production():
            url = secrets_manager.get_secret("postgresql-connection-string", "DATABASE_URL")
            return url or self.database_url
        return self.database_url
```

---

### Step 8: Create Docker Compose for Local Dev

**File: `docker-compose.dev.yml` (NEW)**

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: amplifier-postgres-dev
    environment:
      POSTGRES_USER: amplifier_dev
      POSTGRES_PASSWORD: dev_password
      POSTGRES_DB: amplifier_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_dev_data:/var/lib/postgresql/data
      - ./scripts/init-dev-db.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U amplifier_dev"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_dev_data:
```

**File: `scripts/init-dev-db.sql` (NEW)**

```sql
-- Development database initialization
-- This runs once when the container is first created

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create helper function for updated_at triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Schema will be created by application on first run
```

---

### Step 9: Create Environment Files

**File: `.env.development` (NEW)**

```bash
# Environment
ENVIRONMENT=development

# Service Settings
SERVICE_HOST=0.0.0.0
SERVICE_PORT=8765
SERVICE_WORKERS=1
LOG_LEVEL=debug

# Database - Local PostgreSQL in Docker
DATABASE_URL=postgresql+asyncpg://amplifier_dev:dev_password@localhost:5432/amplifier_dev
DATABASE_POOL_MIN_SIZE=2
DATABASE_POOL_MAX_SIZE=5

# Security (weak credentials OK for local)
SECRET_KEY=development-secret-key-not-secure
AUTH_REQUIRED=false

# CORS (allow all local ports)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:8080

# API Keys
ANTHROPIC_API_KEY=your-key-here
OPENAI_API_KEY=
AZURE_OPENAI_API_KEY=
GOOGLE_API_KEY=

# Session Storage
SESSION_STORAGE_PATH=./sessions
MAX_SESSION_AGE_DAYS=7

# Rate Limiting (very relaxed for local dev)
RATE_LIMIT_REQUESTS_PER_MINUTE=1000

# Telemetry
TELEMETRY_ENABLED=true
TELEMETRY_ENVIRONMENT=development
TELEMETRY_ENABLE_DEV_LOGGER=true
```

**File: `.env.test` (NEW)**

```bash
# Environment
ENVIRONMENT=test

# Database - Azure PostgreSQL Test Instance
DATABASE_URL=postgresql+asyncpg://amplifier_admin:${POSTGRES_PASSWORD}@amplifier-db-test.postgres.database.azure.com:5432/amplifier_test?sslmode=require
DATABASE_POOL_MIN_SIZE=5
DATABASE_POOL_MAX_SIZE=10

# Security (loaded from GitHub Secrets)
SECRET_KEY=${SECRET_KEY}
AUTH_REQUIRED=true

# Telemetry
TELEMETRY_ENABLED=true
TELEMETRY_ENVIRONMENT=test
TELEMETRY_APP_INSIGHTS_CONNECTION_STRING=${APP_INSIGHTS_CONNECTION_STRING}
```

**Update: `.env.example`**

Add new PostgreSQL and environment fields.

---

### Step 10: Update Tests

**File: `tests/conftest.py`**

Add PostgreSQL test fixtures:

```python
import pytest
import asyncpg
from typing import AsyncGenerator

@pytest.fixture
async def test_db_pool() -> AsyncGenerator[asyncpg.Pool, None]:
    """Create test database pool."""
    pool = await asyncpg.create_pool(
        "postgresql://amplifier_dev:dev_password@localhost:5432/amplifier_test",
        min_size=2,
        max_size=5
    )
    
    # Clean database before tests
    async with pool.acquire() as conn:
        # Drop and recreate schema
        await conn.execute('DROP SCHEMA IF EXISTS public CASCADE')
        await conn.execute('CREATE SCHEMA public')
        
        # Initialize schema
        from amplifier_app_api.storage.schema import INIT_SCHEMA
        await conn.execute(INIT_SCHEMA)
    
    yield pool
    
    await pool.close()
```

---

## Testing Checklist

### Local Development Testing

1. **Start PostgreSQL:**
   ```bash
   docker compose -f docker-compose.dev.yml up -d postgres
   ```

2. **Set environment:**
   ```bash
   export ENVIRONMENT=development
   ```

3. **Run API:**
   ```bash
   uvicorn amplifier_app_api.main:app --reload
   ```

4. **Verify schema creation:**
   ```bash
   docker exec amplifier-postgres-dev psql -U amplifier_dev -d amplifier_dev -c '\dt'
   ```

5. **Test CRUD operations:**
   - Create config
   - Create session (with user_id)
   - Verify session_participants entry created
   - Query user's sessions

### Test Environment Testing

1. **Set environment:**
   ```bash
   export ENVIRONMENT=test
   export POSTGRES_PASSWORD="your-test-db-password"
   ```

2. **Test connection:**
   ```bash
   psql "postgresql://amplifier_admin:${POSTGRES_PASSWORD}@amplifier-db-test.postgres.database.azure.com:5432/amplifier_test?sslmode=require"
   ```

3. **Run integration tests:**
   ```bash
   pytest tests/ -v
   ```

---

## Rollback Plan

If issues arise during implementation:

1. **Keep SQLite code in a branch:**
   ```bash
   git checkout -b backup/sqlite-implementation
   git push origin backup/sqlite-implementation
   ```

2. **Revert to SQLite:**
   ```bash
   git revert <commit-hash>
   # Or restore from backup branch
   ```

3. **Switch database URL:**
   ```bash
   DATABASE_URL=sqlite+aiosqlite:///./amplifier.db
   ```

---

## Success Criteria

- [ ] Local PostgreSQL running in Docker
- [ ] API connects to PostgreSQL successfully
- [ ] Schema auto-creates on first connection
- [ ] All tables created with correct structure
- [ ] session_participants table created
- [ ] Session creation includes user_id and participant entry
- [ ] JSON fields (transcript, tags, metadata) work without manual serialization
- [ ] All existing API endpoints work
- [ ] Tests pass against PostgreSQL
- [ ] Connection pooling working (check logs)
- [ ] Can connect to Azure test database
- [ ] Environment-based configuration works
- [ ] Key Vault integration ready (even if not used yet)

---

## Implementation Order

**Recommended order to minimize breakage:**

1. ✅ Create documentation (completed)
2. Update dependencies (pyproject.toml)
3. Create schema.py
4. Create secrets.py (Key Vault integration)
5. Update config.py (environment-based)
6. Create .env.development, .env.test
7. Update database.py (asyncpg refactor) - **BIGGEST CHANGE**
8. Update session_manager.py (pass user_id)
9. Create session_participant.py model
10. Add participant endpoints (optional for now)
11. Create docker-compose.dev.yml
12. Update tests
13. Test locally
14. Test against Azure

**Estimated Total Time:** 4-6 hours for full implementation + testing

---

## Next Steps

Ready to start implementation? I can:

1. **Start with dependencies** - Update pyproject.toml and install asyncpg
2. **Create schema file** - Complete PostgreSQL schema definitions
3. **Refactor database.py** - Full asyncpg migration (this is the big one)
4. **Create environment files** - Set up .env.development and others
5. **Update tests** - PostgreSQL test fixtures

Which would you like to start with?
