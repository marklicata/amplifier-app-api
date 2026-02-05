# Azure Database Migration Plan

## Executive Summary

**Migration:** SQLite → Azure Database for PostgreSQL Flexible Server  
**Timeline:** 2-3 weeks for complete migration  
**Cost:** ~$60/month (B2s tier) starting point  
**Key Benefit:** Multi-user session collaboration support, superior JSON handling, production-ready scalability

---

## 1. Azure Database Service Selection

### Recommended Service: Azure Database for PostgreSQL Flexible Server

**Why PostgreSQL?**

| Requirement | PostgreSQL Advantage |
|-------------|---------------------|
| **Async Python** | Best-in-class `asyncpg` library (fastest, most mature) |
| **JSON Storage** | Native JSONB with binary storage and GIN indexing |
| **Current Architecture** | Minimal code changes from SQLite (similar SQL syntax) |
| **Multi-user Sessions** | LISTEN/NOTIFY pub/sub, row-level locking, advisory locks |
| **Full-text Search** | Built-in tsvector/tsquery for transcript search |
| **FastAPI Ecosystem** | Industry standard, excellent documentation |

**Recommended Tier:** Burstable B2s
- 2 vCores, 4 GB RAM
- 32 GB storage
- ~$60/month
- Production-ready for moderate traffic
- Easy vertical scaling path

---

## 2. Schema Design for Azure PostgreSQL

### 2.1 Core Tables (Migrated from SQLite)

#### Table: `configs`
**Purpose:** Store YAML bundle configurations

```sql
CREATE TABLE configs (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    yaml_content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tags JSONB DEFAULT '{}'::jsonb
);

-- Indexes
CREATE INDEX idx_configs_name ON configs(name);
CREATE INDEX idx_configs_created_at ON configs(created_at);
CREATE INDEX idx_configs_tags ON configs USING GIN(tags);

-- Trigger for updated_at
CREATE TRIGGER update_configs_updated_at
    BEFORE UPDATE ON configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

**Changes from SQLite:**
- `config_id`: TEXT → UUID (native type)
- `tags`: TEXT (JSON string) → JSONB (binary, indexed)
- Added GIN index on tags for efficient JSON queries
- Auto-updating updated_at trigger

---

#### Table: `sessions`
**Purpose:** Store session instances with transcripts

```sql
CREATE TABLE sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_id UUID NOT NULL REFERENCES configs(config_id) ON DELETE CASCADE,
    owner_user_id UUID,  -- Primary owner (for backward compatibility)
    created_by_app_id VARCHAR(100),
    last_accessed_by_app_id VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ,
    message_count INTEGER NOT NULL DEFAULT 0,
    transcript JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,  -- New: extensible metadata
    
    CONSTRAINT sessions_status_check CHECK (status IN ('active', 'completed', 'failed', 'cancelled'))
);

-- Indexes
CREATE INDEX idx_sessions_config_id ON sessions(config_id);
CREATE INDEX idx_sessions_owner_user_id ON sessions(owner_user_id);
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_created_at ON sessions(created_at);
CREATE INDEX idx_sessions_transcript ON sessions USING GIN(transcript);  -- For JSON queries
CREATE INDEX idx_sessions_metadata ON sessions USING GIN(metadata);

-- Trigger
CREATE TRIGGER update_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

**Changes from SQLite:**
- `session_id`, `config_id`: TEXT → UUID
- `user_id`: Renamed to `owner_user_id` for clarity (primary owner)
- `transcript`: TEXT (JSON string) → JSONB with GIN index
- Added `metadata` JSONB column for extensibility
- Added `ON DELETE CASCADE` for config foreign key
- Added CHECK constraint for status enum
- GIN indexes on JSONB columns for efficient queries

---

#### Table: `session_participants` ⭐ **NEW**
**Purpose:** Enable multi-user session collaboration (many-to-many)

```sql
CREATE TABLE session_participants (
    session_id UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'viewer',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at TIMESTAMPTZ,
    permissions JSONB DEFAULT '{}'::jsonb,
    
    PRIMARY KEY (session_id, user_id),
    CONSTRAINT session_participants_role_check CHECK (role IN ('owner', 'editor', 'viewer'))
);

-- Indexes
CREATE INDEX idx_session_participants_user_id ON session_participants(user_id);
CREATE INDEX idx_session_participants_session_id ON session_participants(session_id);
CREATE INDEX idx_session_participants_last_active ON session_participants(last_active_at);
```

**Purpose:**
- Supports multiple users per session (future requirement)
- Tracks role-based access (owner, editor, viewer)
- Preserves audit trail (joined_at, last_active_at)
- Extensible permissions via JSONB

**Migration Strategy:**
- Populate from `sessions.owner_user_id` during migration
- All existing sessions get owner as participant with 'owner' role

---

#### Table: `applications`
**Purpose:** API key authentication for multi-tenant access

```sql
CREATE TABLE applications (
    app_id VARCHAR(100) PRIMARY KEY,
    app_name VARCHAR(255) NOT NULL,
    api_key_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    settings JSONB DEFAULT '{}'::jsonb
);

-- Trigger
CREATE TRIGGER update_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

**Changes from SQLite:**
- `is_active`: INTEGER (0/1) → BOOLEAN (native type)
- `settings`: TEXT (JSON string) → JSONB
- Timestamps converted to TIMESTAMPTZ

---

#### Table: `users`
**Purpose:** User analytics and metadata tracking

```sql
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_app_id VARCHAR(100),
    total_sessions INTEGER NOT NULL DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb,  -- Email, name, etc. from JWT
    
    CONSTRAINT users_total_sessions_check CHECK (total_sessions >= 0)
);

-- Indexes
CREATE INDEX idx_users_last_seen ON users(last_seen);
CREATE INDEX idx_users_metadata ON users USING GIN(metadata);
```

**Changes from SQLite:**
- `user_id`: TEXT → UUID
- `metadata`: TEXT (JSON string) → JSONB with GIN index
- Added CHECK constraint for total_sessions

---

#### Table: `configuration`
**Purpose:** App-level key-value settings

```sql
CREATE TABLE configuration (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL,
    scope VARCHAR(100) NOT NULL DEFAULT 'global',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_configuration_scope ON configuration(scope);

-- Trigger
CREATE TRIGGER update_configuration_updated_at
    BEFORE UPDATE ON configuration
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

**Changes from SQLite:**
- `value`: TEXT (JSON string) → JSONB
- Timestamps converted to TIMESTAMPTZ

---

### 2.2 Helper Functions & Triggers

```sql
-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

---

## 3. Multi-User Session Architecture

### Current State (1:1 User-Session)

```
users (1) ←──[owner_user_id]──→ (1) sessions
```

**Problem:** Locks one user per session, prevents collaboration

---

### Future State (Many-to-Many with Roles)

```
users (N) ←──[session_participants]──→ (N) sessions
```

**Benefits:**
- Multiple users can access same session
- Role-based permissions (owner, editor, viewer)
- Preserves backward compatibility (owner_user_id still exists)
- Audit trail of who joined when

---

### Usage Patterns

#### Current Usage (Backward Compatible)
```python
# Get user's owned sessions
sessions = await conn.fetch(
    'SELECT * FROM sessions WHERE owner_user_id = $1',
    user_id
)
```

#### Future Usage (Multi-User)
```python
# Get all sessions user participates in
sessions = await conn.fetch('''
    SELECT s.*, sp.role, sp.joined_at
    FROM sessions s
    JOIN session_participants sp ON s.session_id = sp.session_id
    WHERE sp.user_id = $1
    ORDER BY sp.last_active_at DESC
''', user_id)

# Add participant to session
await conn.execute('''
    INSERT INTO session_participants (session_id, user_id, role)
    VALUES ($1, $2, $3)
    ON CONFLICT (session_id, user_id) DO UPDATE
    SET last_active_at = NOW()
''', session_id, user_id, 'editor')

# Check user's permission
role = await conn.fetchval('''
    SELECT role FROM session_participants
    WHERE session_id = $1 AND user_id = $2
''', session_id, user_id)
```

---

## 4. Migration Strategy

### Phase 1: Provision Infrastructure (Week 1)

**Tasks:**
1. Create Azure PostgreSQL Flexible Server (B2s tier)
2. Configure firewall rules for App Service
3. Enable SSL/TLS enforcement
4. Set up Azure Key Vault for connection strings
5. Configure managed identity for Key Vault access
6. Enable diagnostic logging and monitoring

**Azure MCP Commands:**
```
"Create PostgreSQL Flexible Server named 'amplifier-db-prod' in resource group 'rg-amplifier' 
in East US with Burstable B2s tier, PostgreSQL 15, 32GB storage, admin user 'dbadmin'"

"Create database 'amplifier_db' on PostgreSQL server 'amplifier-db-prod'"

"Add firewall rule to PostgreSQL server 'amplifier-db-prod' allowing Azure services"

"Store PostgreSQL connection string in Key Vault 'kv-amplifier'"
```

---

### Phase 2: Schema Migration (Week 1-2)

**Tasks:**
1. Create PostgreSQL schema with new design
2. Create migration script (SQLite → PostgreSQL)
3. Test migration on dev environment
4. Populate session_participants from owner_user_id
5. Add GIN indexes for JSON columns
6. Set up triggers for updated_at columns

**Migration Script:**
```python
# See detailed migration script in Section 5 below
```

---

### Phase 3: Application Code Updates (Week 2)

**Tasks:**
1. Replace `aiosqlite` with `asyncpg`
2. Update Database class with asyncpg connection pooling
3. Remove manual JSON serialization (asyncpg handles automatically)
4. Update UUID handling (native type vs string)
5. Update timestamp handling (timezone-aware)
6. Add session_participants operations
7. Update queries to use JSONB operators

**Code Changes:**
- `storage/database.py`: Replace aiosqlite with asyncpg
- `core/session_manager.py`: Add user_id parameter to create_session
- `api/sessions.py`: Add participant management endpoints
- `models/session.py`: Add SessionParticipant model

---

### Phase 4: Testing & Deployment (Week 2-3)

**Tasks:**
1. Run integration tests against PostgreSQL
2. Performance testing (connection pooling, JSON queries)
3. Test multi-user session scenarios
4. Migrate production data
5. Deploy updated application
6. Monitor for issues

---

## 5. Detailed Migration Script

### 5.1 Python Migration Script

```python
import asyncio
import aiosqlite
import asyncpg
import json
import uuid
from datetime import datetime
from typing import Dict, Any

async def migrate_sqlite_to_postgres():
    """Migrate SQLite database to Azure PostgreSQL"""
    
    # Configuration
    SQLITE_PATH = './amplifier.db'
    POSTGRES_DSN = 'postgresql://user:pass@server.postgres.database.azure.com/amplifier_db'
    
    print("Starting migration...")
    
    # Connect to databases
    sqlite_conn = await aiosqlite.connect(SQLITE_PATH)
    sqlite_conn.row_factory = aiosqlite.Row
    pg_pool = await asyncpg.create_pool(POSTGRES_DSN, min_size=5, max_size=10)
    
    try:
        async with pg_pool.acquire() as pg_conn:
            # Start transaction
            async with pg_conn.transaction():
                
                # 1. Migrate configs table
                print("Migrating configs...")
                async with sqlite_conn.execute('SELECT * FROM configs') as cursor:
                    async for row in cursor:
                        # Parse JSON fields
                        tags = json.loads(row['tags']) if row['tags'] else {}
                        
                        await pg_conn.execute('''
                            INSERT INTO configs (config_id, name, description, yaml_content, 
                                                created_at, updated_at, tags)
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ''', 
                            uuid.UUID(row['config_id']),
                            row['name'],
                            row['description'],
                            row['yaml_content'],
                            datetime.fromisoformat(row['created_at']),
                            datetime.fromisoformat(row['updated_at']),
                            tags
                        )
                print(f"  ✓ Migrated {await pg_conn.fetchval('SELECT COUNT(*) FROM configs')} configs")
                
                # 2. Migrate applications table
                print("Migrating applications...")
                async with sqlite_conn.execute('SELECT * FROM applications') as cursor:
                    async for row in cursor:
                        settings = json.loads(row['settings']) if row['settings'] else {}
                        
                        await pg_conn.execute('''
                            INSERT INTO applications (app_id, app_name, api_key_hash, 
                                                     is_active, created_at, updated_at, settings)
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ''',
                            row['app_id'],
                            row['app_name'],
                            row['api_key_hash'],
                            bool(row['is_active']),
                            datetime.fromisoformat(row['created_at']),
                            datetime.fromisoformat(row['updated_at']),
                            settings
                        )
                print(f"  ✓ Migrated {await pg_conn.fetchval('SELECT COUNT(*) FROM applications')} applications")
                
                # 3. Migrate users table
                print("Migrating users...")
                async with sqlite_conn.execute('SELECT * FROM users') as cursor:
                    async for row in cursor:
                        metadata = json.loads(row['metadata']) if row['metadata'] else {}
                        
                        await pg_conn.execute('''
                            INSERT INTO users (user_id, first_seen, last_seen, 
                                             last_seen_app_id, total_sessions, metadata)
                            VALUES ($1, $2, $3, $4, $5, $6)
                        ''',
                            uuid.UUID(row['user_id']) if row['user_id'] else None,
                            datetime.fromisoformat(row['first_seen']),
                            datetime.fromisoformat(row['last_seen']),
                            row['last_seen_app_id'],
                            row['total_sessions'],
                            metadata
                        )
                print(f"  ✓ Migrated {await pg_conn.fetchval('SELECT COUNT(*) FROM users')} users")
                
                # 4. Migrate sessions table
                print("Migrating sessions...")
                session_count = 0
                async with sqlite_conn.execute('SELECT * FROM sessions') as cursor:
                    async for row in cursor:
                        # Parse JSON transcript
                        transcript = json.loads(row['transcript']) if row['transcript'] else []
                        
                        # Handle NULL user_id (from legacy sessions)
                        owner_user_id = None
                        if row['user_id'] and row['user_id'] != 'legacy-user':
                            try:
                                owner_user_id = uuid.UUID(row['user_id'])
                            except (ValueError, AttributeError):
                                owner_user_id = None
                        
                        await pg_conn.execute('''
                            INSERT INTO sessions (session_id, config_id, owner_user_id,
                                                created_by_app_id, last_accessed_by_app_id,
                                                status, created_at, updated_at, last_accessed_at,
                                                message_count, transcript, metadata)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                        ''',
                            uuid.UUID(row['session_id']),
                            uuid.UUID(row['config_id']),
                            owner_user_id,
                            row['created_by_app_id'] if row['created_by_app_id'] != 'legacy-app' else None,
                            row['last_accessed_by_app_id'],
                            row['status'],
                            datetime.fromisoformat(row['created_at']),
                            datetime.fromisoformat(row['updated_at']),
                            datetime.fromisoformat(row['last_accessed_at']) if row['last_accessed_at'] else None,
                            row['message_count'],
                            transcript,
                            {}  # Empty metadata
                        )
                        session_count += 1
                print(f"  ✓ Migrated {session_count} sessions")
                
                # 5. Populate session_participants from owner_user_id
                print("Creating session_participants from session owners...")
                participant_count = await pg_conn.fetchval('''
                    INSERT INTO session_participants (session_id, user_id, role, joined_at)
                    SELECT session_id, owner_user_id, 'owner', created_at
                    FROM sessions
                    WHERE owner_user_id IS NOT NULL
                    RETURNING COUNT(*)
                ''')
                print(f"  ✓ Created {participant_count} session participants")
                
                # 6. Migrate configuration table
                print("Migrating configuration...")
                async with sqlite_conn.execute('SELECT * FROM configuration') as cursor:
                    async for row in cursor:
                        value = json.loads(row['value'])
                        
                        await pg_conn.execute('''
                            INSERT INTO configuration (key, value, scope, updated_at)
                            VALUES ($1, $2, $3, $4)
                        ''',
                            row['key'],
                            value,
                            row['scope'],
                            datetime.fromisoformat(row['updated_at'])
                        )
                print(f"  ✓ Migrated {await pg_conn.fetchval('SELECT COUNT(*) FROM configuration')} settings")
                
        print("\n✅ Migration completed successfully!")
        
        # Print summary
        async with pg_pool.acquire() as pg_conn:
            print("\n📊 Migration Summary:")
            print(f"  Configs: {await pg_conn.fetchval('SELECT COUNT(*) FROM configs')}")
            print(f"  Applications: {await pg_conn.fetchval('SELECT COUNT(*) FROM applications')}")
            print(f"  Users: {await pg_conn.fetchval('SELECT COUNT(*) FROM users')}")
            print(f"  Sessions: {await pg_conn.fetchval('SELECT COUNT(*) FROM sessions')}")
            print(f"  Session Participants: {await pg_conn.fetchval('SELECT COUNT(*) FROM session_participants')}")
            print(f"  Configuration: {await pg_conn.fetchval('SELECT COUNT(*) FROM configuration')}")
    
    finally:
        await sqlite_conn.close()
        await pg_pool.close()

if __name__ == '__main__':
    asyncio.run(migrate_sqlite_to_postgres())
```

---

## 6. Application Code Changes

### 6.1 Update Database Connection (storage/database.py)

**Before (SQLite + aiosqlite):**
```python
import aiosqlite

class Database:
    async def connect(self):
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
```

**After (PostgreSQL + asyncpg):**
```python
import asyncpg
from typing import Optional

class Database:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        self._pool = await asyncpg.create_pool(
            self.dsn,
            min_size=10,
            max_size=20,
            command_timeout=60
        )
    
    async def disconnect(self):
        if self._pool:
            await self._pool.close()
    
    async def fetch(self, query: str, *args):
        async with self._pool.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args):
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def execute(self, query: str, *args):
        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)
```

---

### 6.2 Update Session Creation (storage/database.py)

**Before:**
```python
async def create_session(self, session_id: str, config_id: str, status: str):
    await self._connection.execute(
        '''INSERT INTO sessions (session_id, config_id, status, created_at, updated_at, 
                                 message_count, transcript)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (session_id, config_id, status, now, now, 0, json.dumps([]))
    )
    await self._connection.commit()
```

**After:**
```python
async def create_session(
    self,
    session_id: uuid.UUID,
    config_id: uuid.UUID,
    owner_user_id: Optional[uuid.UUID],
    status: str,
    created_by_app_id: Optional[str] = None
):
    async with self._pool.acquire() as conn:
        async with conn.transaction():
            # Create session
            await conn.execute('''
                INSERT INTO sessions (session_id, config_id, owner_user_id, 
                                     created_by_app_id, status, message_count, transcript)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            ''', session_id, config_id, owner_user_id, created_by_app_id, status, 0, [])
            
            # Add owner as participant (if user_id provided)
            if owner_user_id:
                await conn.execute('''
                    INSERT INTO session_participants (session_id, user_id, role)
                    VALUES ($1, $2, $3)
                ''', session_id, owner_user_id, 'owner')
```

**Key Changes:**
- Added `owner_user_id` parameter (currently missing)
- Added `created_by_app_id` parameter (for tracking)
- Automatically creates session_participant entry for owner
- Uses asyncpg parameter style ($1, $2) instead of SQLite (?, ?)
- No manual JSON serialization (asyncpg handles dict → JSONB)
- Transaction ensures atomicity

---

### 6.3 Update JSON Queries (No More Manual Serialization)

**Before (SQLite):**
```python
# Manual JSON serialization
transcript_json = json.dumps(transcript_list)
await conn.execute(
    'UPDATE sessions SET transcript = ? WHERE session_id = ?',
    (transcript_json, session_id)
)

# Manual JSON deserialization
row = await conn.fetchone('SELECT transcript FROM sessions WHERE session_id = ?', (session_id,))
transcript = json.loads(row['transcript'])
```

**After (PostgreSQL + asyncpg):**
```python
# Automatic JSON handling
await conn.execute(
    'UPDATE sessions SET transcript = $1 WHERE session_id = $2',
    transcript_list, session_id  # asyncpg auto-converts dict/list to JSONB
)

# Automatic JSON deserialization
row = await conn.fetchrow('SELECT transcript FROM sessions WHERE session_id = $1', session_id)
transcript = row['transcript']  # Already a Python list/dict!
```

---

### 6.4 Add Session Participant Operations

**New methods in storage/database.py:**

```python
async def add_session_participant(
    self,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str = 'viewer'
):
    """Add a user to a session with specified role"""
    async with self._pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO session_participants (session_id, user_id, role)
            VALUES ($1, $2, $3)
            ON CONFLICT (session_id, user_id) DO UPDATE
            SET last_active_at = NOW()
        ''', session_id, user_id, role)

async def remove_session_participant(
    self,
    session_id: uuid.UUID,
    user_id: uuid.UUID
):
    """Remove a user from a session"""
    async with self._pool.acquire() as conn:
        await conn.execute('''
            DELETE FROM session_participants
            WHERE session_id = $1 AND user_id = $2
        ''', session_id, user_id)

async def get_session_participants(
    self,
    session_id: uuid.UUID
) -> list[dict]:
    """Get all participants for a session"""
    async with self._pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT user_id, role, joined_at, last_active_at, permissions
            FROM session_participants
            WHERE session_id = $1
            ORDER BY joined_at
        ''', session_id)
        return [dict(row) for row in rows]

async def get_user_sessions(
    self,
    user_id: uuid.UUID
) -> list[dict]:
    """Get all sessions a user participates in"""
    async with self._pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT s.*, sp.role, sp.joined_at, sp.last_active_at
            FROM sessions s
            JOIN session_participants sp ON s.session_id = sp.session_id
            WHERE sp.user_id = $1
            ORDER BY sp.last_active_at DESC NULLS LAST
        ''', user_id)
        return [dict(row) for row in rows]

async def update_participant_role(
    self,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str
):
    """Update a participant's role"""
    async with self._pool.acquire() as conn:
        await conn.execute('''
            UPDATE session_participants
            SET role = $1, last_active_at = NOW()
            WHERE session_id = $2 AND user_id = $3
        ''', role, session_id, user_id)
```

---

## 7. Configuration Updates

### 7.1 Update config.py

**Before:**
```python
DATABASE_URL = "sqlite+aiosqlite:///./amplifier.db"
```

**After:**
```python
import os
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# Load from Azure Key Vault
def get_database_url() -> str:
    if os.getenv('ENVIRONMENT') == 'production':
        # Load from Key Vault using managed identity
        credential = DefaultAzureCredential()
        vault_url = os.getenv('AZURE_KEYVAULT_URL')
        client = SecretClient(vault_url=vault_url, credential=credential)
        secret = client.get_secret('postgresql-connection-string')
        return secret.value
    else:
        # Local development
        return os.getenv('DATABASE_URL', 'postgresql+asyncpg://localhost/amplifier_dev')

DATABASE_URL = get_database_url()
```

**Environment Variables:**
```bash
# .env.production
ENVIRONMENT=production
AZURE_KEYVAULT_URL=https://kv-amplifier.vault.azure.net/

# .env.development
DATABASE_URL=postgresql+asyncpg://localhost:5432/amplifier_dev
```

---

### 7.2 Update pyproject.toml Dependencies

**Remove:**
```toml
aiosqlite = "^0.19.0"
```

**Add:**
```toml
asyncpg = "^0.29.0"
azure-identity = "^1.15.0"
azure-keyvault-secrets = "^4.7.0"
```

---

## 8. Testing Strategy

### 8.1 Integration Tests

**Test file: tests/test_postgres_migration.py**

```python
import pytest
import asyncpg
from uuid import uuid4

@pytest.mark.asyncio
async def test_session_creation_with_participant():
    """Test that session creation automatically adds participant"""
    pool = await asyncpg.create_pool(TEST_DSN)
    
    session_id = uuid4()
    user_id = uuid4()
    config_id = uuid4()
    
    async with pool.acquire() as conn:
        # Create session with owner
        await conn.execute('''
            INSERT INTO sessions (session_id, config_id, owner_user_id, status)
            VALUES ($1, $2, $3, $4)
        ''', session_id, config_id, user_id, 'active')
        
        await conn.execute('''
            INSERT INTO session_participants (session_id, user_id, role)
            VALUES ($1, $2, $3)
        ''', session_id, user_id, 'owner')
        
        # Verify participant was created
        role = await conn.fetchval('''
            SELECT role FROM session_participants
            WHERE session_id = $1 AND user_id = $2
        ''', session_id, user_id)
        
        assert role == 'owner'
    
    await pool.close()

@pytest.mark.asyncio
async def test_multi_user_session():
    """Test multiple users accessing same session"""
    pool = await asyncpg.create_pool(TEST_DSN)
    
    session_id = uuid4()
    owner_id = uuid4()
    viewer_id = uuid4()
    
    async with pool.acquire() as conn:
        # Create session
        await conn.execute('''
            INSERT INTO sessions (session_id, config_id, owner_user_id, status)
            VALUES ($1, $2, $3, $4)
        ''', session_id, uuid4(), owner_id, 'active')
        
        # Add owner as participant
        await conn.execute('''
            INSERT INTO session_participants (session_id, user_id, role)
            VALUES ($1, $2, $3)
        ''', session_id, owner_id, 'owner')
        
        # Add viewer
        await conn.execute('''
            INSERT INTO session_participants (session_id, user_id, role)
            VALUES ($1, $2, $3)
        ''', session_id, viewer_id, 'viewer')
        
        # Verify both users have access
        participants = await conn.fetch('''
            SELECT user_id, role FROM session_participants
            WHERE session_id = $1
            ORDER BY role DESC
        ''', session_id)
        
        assert len(participants) == 2
        assert participants[0]['role'] == 'owner'
        assert participants[1]['role'] == 'viewer'
    
    await pool.close()

@pytest.mark.asyncio
async def test_jsonb_transcript_query():
    """Test JSONB querying on transcript"""
    pool = await asyncpg.create_pool(TEST_DSN)
    
    session_id = uuid4()
    transcript = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"}
    ]
    
    async with pool.acquire() as conn:
        # Insert with JSONB transcript
        await conn.execute('''
            INSERT INTO sessions (session_id, config_id, transcript, status)
            VALUES ($1, $2, $3, $4)
        ''', session_id, uuid4(), transcript, 'active')
        
        # Query with JSONB operators
        result = await conn.fetchval('''
            SELECT transcript @> $1
            FROM sessions
            WHERE session_id = $2
        ''', [{"role": "user"}], session_id)
        
        assert result is True  # Transcript contains user message
    
    await pool.close()
```

---

## 9. Deployment Checklist

### Pre-Deployment
- [ ] Provision Azure PostgreSQL Flexible Server
- [ ] Configure firewall rules
- [ ] Set up Azure Key Vault
- [ ] Store connection string in Key Vault
- [ ] Create PostgreSQL schema
- [ ] Test migration script on dev environment
- [ ] Update application code
- [ ] Run integration tests
- [ ] Performance testing

### Deployment Day
- [ ] Backup SQLite database
- [ ] Put application in maintenance mode
- [ ] Run migration script
- [ ] Verify data integrity
- [ ] Deploy updated application
- [ ] Test critical paths
- [ ] Monitor logs for errors
- [ ] Remove maintenance mode

### Post-Deployment
- [ ] Monitor Application Insights
- [ ] Check slow query logs
- [ ] Verify connection pool metrics
- [ ] Set up alerting rules
- [ ] Document rollback procedure
- [ ] Schedule backup verification

---

## 10. Cost Analysis

### Monthly Costs (B2s Tier)

| Component | Cost |
|-----------|------|
| Compute (B2s - 2vCore, 4GB) | $45 |
| Storage (32 GB) | $4 |
| Backup Storage (32 GB, 7 days) | $2 |
| Network Egress | $5-10 |
| **Total** | **~$56-61/month** |

### Scaling Costs

| Tier | vCores | RAM | Storage | Monthly Cost |
|------|--------|-----|---------|--------------|
| **B2s** (Starting) | 2 | 4 GB | 32 GB | $60 |
| D2s_v3 | 2 | 8 GB | 128 GB | $120 |
| D4s_v3 | 4 | 16 GB | 256 GB | $240 |
| D8s_v3 | 8 | 32 GB | 512 GB | $480 |

---

## 11. Rollback Plan

If migration fails or issues arise:

### Immediate Rollback (Day 1)
1. Revert application deployment to SQLite version
2. Point DATABASE_URL back to SQLite
3. SQLite database still intact (was copied, not moved)
4. No data loss

### Long-term Rollback (After Data Added)
1. Keep SQLite database operational for 30 days
2. Export PostgreSQL data back to SQLite if needed
3. Use reverse migration script (PostgreSQL → SQLite)

**Recommendation:** Run dual databases for 2 weeks to validate before decommissioning SQLite.

---

## 12. Success Metrics

- [ ] Zero data loss during migration
- [ ] All existing API endpoints work correctly
- [ ] Session creation includes user_id and participant
- [ ] JSON queries faster with JSONB indexes
- [ ] Connection pool stable under load
- [ ] P95 latency < 100ms for session queries
- [ ] Multi-user session support ready for future

---

## 13. Future Enhancements (Post-Migration)

Once PostgreSQL is live, these features become easy:

### Full-Text Search on Transcripts
```sql
-- Add tsvector column
ALTER TABLE sessions ADD COLUMN transcript_search tsvector;

-- Update trigger for automatic search index
CREATE TRIGGER sessions_transcript_search_update
BEFORE INSERT OR UPDATE ON sessions
FOR EACH ROW EXECUTE FUNCTION
  tsvector_update_trigger(transcript_search, 'pg_catalog.english', transcript);

-- Search transcripts
SELECT * FROM sessions
WHERE transcript_search @@ to_tsquery('error & database');
```

### Real-Time Session Collaboration (LISTEN/NOTIFY)
```python
# Subscribe to session updates
await conn.add_listener('session_updates', handle_update)

# Notify other clients of changes
await conn.execute("NOTIFY session_updates, '{}}'".format(json.dumps({
    'session_id': session_id,
    'user_id': user_id,
    'action': 'message_added'
})))
```

### Partial JSON Updates (Efficient)
```sql
-- Append message without rewriting entire transcript
UPDATE sessions
SET transcript = transcript || '[{"role": "user", "content": "New message"}]'::jsonb
WHERE session_id = $1;
```

---

## 14. Open Questions & Decisions Needed

1. **UUID vs Sequential IDs**: Use native UUID or keep string-based IDs?
   - **Recommendation:** Native UUID (better for distributed systems, security)

2. **Session Participant Permissions**: Define specific permissions in JSONB or just roles?
   - **Recommendation:** Start with roles (owner/editor/viewer), add permissions later if needed

3. **Soft Delete vs Hard Delete**: Add `deleted_at` column for sessions?
   - **Recommendation:** Add soft delete for audit trail

4. **Connection Pool Size**: Start with 10-20 or tune based on load?
   - **Recommendation:** Start with 20 max connections, monitor and adjust

5. **Backup Strategy**: Daily automated backups or continuous?
   - **Recommendation:** Daily automated (7-day retention), enable point-in-time restore

---

## Summary

This migration plan provides a **complete path from SQLite to Azure PostgreSQL** with:

✅ **Future-proof schema** supporting multi-user sessions  
✅ **Minimal code changes** (asyncpg is similar to aiosqlite)  
✅ **Production-ready** from day one (B2s tier)  
✅ **Clear migration path** with detailed scripts  
✅ **Backward compatible** (owner_user_id preserved)  
✅ **Extensible** (JSONB metadata columns, permissions)  

**Timeline:** 2-3 weeks from start to production deployment  
**Risk:** Low (can run dual databases during transition)  
**Cost:** ~$60/month starting point (scales up as needed)

Ready to proceed with Phase 1 (infrastructure provisioning)?
