"""PostgreSQL schema definitions for Amplifier API."""

# Helper function for auto-updating timestamps
CREATE_UPDATED_AT_TRIGGER = """
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

# Configs table - stores JSON bundle configurations (without user_id initially)
CREATE_CONFIGS_TABLE = """
CREATE TABLE IF NOT EXISTS configs (
    config_id TEXT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    config_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tags JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_configs_name ON configs(name);
CREATE INDEX IF NOT EXISTS idx_configs_created_at ON configs(created_at);
CREATE INDEX IF NOT EXISTS idx_configs_tags ON configs USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_configs_config_json ON configs USING GIN(config_json);

DROP TRIGGER IF EXISTS update_configs_updated_at ON configs;
CREATE TRIGGER update_configs_updated_at
    BEFORE UPDATE ON configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
"""

# Migration: Add user_id column to existing configs table if it doesn't exist
MIGRATE_CONFIGS_ADD_USER_ID = """
DO $$
BEGIN
    -- Add user_id column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'configs' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE configs ADD COLUMN user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS idx_configs_user_id ON configs(user_id);
    END IF;
END $$;
"""

# Migration: Rename yaml_content to config_json and convert to JSONB
MIGRATE_CONFIGS_YAML_TO_JSON = """
DO $$
BEGIN
    -- Check if yaml_content column exists (old schema)
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'configs' AND column_name = 'yaml_content'
    ) THEN
        -- Rename column and convert to JSONB (this will fail if data isn't valid JSON)
        ALTER TABLE configs RENAME COLUMN yaml_content TO config_json;
        ALTER TABLE configs ALTER COLUMN config_json TYPE JSONB USING config_json::jsonb;

        -- Add GIN index for config_json
        CREATE INDEX IF NOT EXISTS idx_configs_config_json ON configs USING GIN(config_json);
    END IF;
END $$;
"""

# Applications table - API key authentication for multi-tenant access
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

# Users table - user analytics and metadata tracking
CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
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

# Sessions table - session instances with transcripts
CREATE_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    config_id TEXT NOT NULL REFERENCES configs(config_id) ON DELETE CASCADE,
    owner_user_id TEXT,
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

# Session participants table - enables multi-user session collaboration
CREATE_SESSION_PARTICIPANTS_TABLE = """
CREATE TABLE IF NOT EXISTS session_participants (
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
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

# Configuration table - app-level key-value settings
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

# Complete schema initialization - executes in order
INIT_SCHEMA = f"""
-- Create helper functions
{CREATE_UPDATED_AT_TRIGGER}

-- Create tables in dependency order
-- Users table must be created before configs (foreign key dependency)
{CREATE_APPLICATIONS_TABLE}
{CREATE_USERS_TABLE}
{CREATE_CONFIGS_TABLE}

-- Run migrations
{MIGRATE_CONFIGS_ADD_USER_ID}
{MIGRATE_CONFIGS_YAML_TO_JSON}

{CREATE_SESSIONS_TABLE}
{CREATE_SESSION_PARTICIPANTS_TABLE}
{CREATE_CONFIGURATION_TABLE}
"""
