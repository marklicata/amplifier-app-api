"""Database migration utilities for authentication features."""

import logging

import aiosqlite

logger = logging.getLogger(__name__)


async def migrate_to_auth(connection: aiosqlite.Connection) -> None:
    """Migrate database to support authentication.

    Adds:
    - applications table
    - users table (optional analytics)
    - user_id, created_by_app_id, last_accessed_by_app_id to sessions
    - last_accessed_at to sessions
    """
    logger.info("Starting authentication migration...")

    # Check if migration already applied
    cursor = await connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='applications'"
    )
    if await cursor.fetchone():
        logger.info("Authentication migration already applied")
        return

    # Create applications table
    await connection.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            app_id TEXT PRIMARY KEY,
            app_name TEXT NOT NULL,
            api_key_hash TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            settings TEXT
        )
    """)

    # Create users table (optional, for analytics)
    await connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            first_seen TIMESTAMP NOT NULL,
            last_seen TIMESTAMP NOT NULL,
            last_seen_app_id TEXT,
            total_sessions INTEGER DEFAULT 0,
            metadata TEXT
        )
    """)

    # Check if sessions table needs migration
    cursor = await connection.execute("PRAGMA table_info(sessions)")
    columns = {row[1] for row in await cursor.fetchall()}

    if "user_id" not in columns:
        logger.info("Adding authentication columns to sessions table...")

        # SQLite doesn't support adding NOT NULL columns with ALTER TABLE
        # So we need to recreate the table

        # 1. Create new sessions table with auth columns
        await connection.execute("""
            CREATE TABLE sessions_new (
                session_id TEXT PRIMARY KEY,
                config_id TEXT NOT NULL,
                user_id TEXT,
                created_by_app_id TEXT,
                last_accessed_by_app_id TEXT,
                status TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                last_accessed_at TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                transcript TEXT,
                FOREIGN KEY (config_id) REFERENCES configs(config_id)
            )
        """)

        # 2. Copy existing data (set default values for new columns)
        await connection.execute("""
            INSERT INTO sessions_new (
                session_id, config_id, user_id, created_by_app_id, 
                last_accessed_by_app_id, status, created_at, updated_at,
                last_accessed_at, message_count, transcript
            )
            SELECT 
                session_id, config_id, 'legacy-user', 'legacy-app',
                NULL, status, created_at, updated_at,
                updated_at, message_count, transcript
            FROM sessions
        """)

        # 3. Drop old table
        await connection.execute("DROP TABLE sessions")

        # 4. Rename new table
        await connection.execute("ALTER TABLE sessions_new RENAME TO sessions")

        # 5. Recreate indexes
        await connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_config_id ON sessions(config_id)"
        )
        await connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)"
        )
        await connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at)"
        )
        await connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)"
        )

        logger.info("Sessions table migrated successfully")

    await connection.commit()
    logger.info("Authentication migration completed")


async def check_migration_status(connection: aiosqlite.Connection) -> dict[str, bool]:
    """Check which migrations have been applied.

    Returns:
        Dictionary with migration status
    """
    status = {}

    # Check for applications table
    cursor = await connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='applications'"
    )
    status["auth_tables"] = await cursor.fetchone() is not None

    # Check for auth columns in sessions
    cursor = await connection.execute("PRAGMA table_info(sessions)")
    columns = {row[1] for row in await cursor.fetchall()}
    status["auth_columns"] = "user_id" in columns

    return status
