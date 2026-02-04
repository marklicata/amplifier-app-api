"""Database management and schema."""

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import aiosqlite

from ..config import settings

logger = logging.getLogger(__name__)

# SQL Schema
SCHEMA_SQL = """
-- Configs table (stores complete YAML bundles)
CREATE TABLE IF NOT EXISTS configs (
    config_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    yaml_content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    tags TEXT
);

-- Sessions table (simplified - references config_id)
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    config_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    message_count INTEGER DEFAULT 0,
    transcript TEXT,
    FOREIGN KEY (config_id) REFERENCES configs(config_id)
);

-- Configuration table (for app-level settings)
CREATE TABLE IF NOT EXISTS configuration (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    scope TEXT DEFAULT 'global',
    updated_at TIMESTAMP NOT NULL
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_configs_name ON configs(name);
CREATE INDEX IF NOT EXISTS idx_configs_created_at ON configs(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_config_id ON sessions(config_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_config_scope ON configuration(scope);
"""


class Database:
    """Async SQLite database manager."""

    def __init__(self, db_path: Path | str):
        """Initialize database connection."""
        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Establish database connection and initialize schema."""
        if self._connection is None:
            self._connection = await aiosqlite.connect(str(self.db_path))
            if self._connection:  # Type guard
                self._connection.row_factory = aiosqlite.Row
                await self._initialize_schema()
                logger.info(f"Database connected: {self.db_path}")

    async def disconnect(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Database disconnected")

    async def _initialize_schema(self) -> None:
        """Initialize database schema."""
        if self._connection:
            await self._connection.executescript(SCHEMA_SQL)
            await self._connection.commit()
            logger.info("Database schema initialized")

    # Session operations
    async def create_session(
        self,
        session_id: str,
        config_id: str,
        status: str,
    ) -> None:
        """Create a new session."""
        if not self._connection:
            raise RuntimeError("Database not connected")

        now = datetime.now(UTC)

        await self._connection.execute(
            """
            INSERT INTO sessions (
                session_id, config_id, status,
                created_at, updated_at, message_count, transcript
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                config_id,
                status,
                now,
                now,
                0,
                json.dumps([]),
            ),
        )
        await self._connection.commit()
        logger.debug(f"Created session: {session_id}")

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session by ID."""
        if not self._connection:
            raise RuntimeError("Database not connected")

        cursor = await self._connection.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        )
        row = await cursor.fetchone()

        if row:
            return {
                "session_id": row["session_id"],
                "config_id": row["config_id"],
                "status": row["status"],
                "created_at": datetime.fromisoformat(row["created_at"]),
                "updated_at": datetime.fromisoformat(row["updated_at"]),
                "message_count": row["message_count"],
                "transcript": json.loads(row["transcript"]) if row["transcript"] else [],
            }
        return None

    async def list_sessions(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """List all sessions."""
        if not self._connection:
            raise RuntimeError("Database not connected")

        cursor = await self._connection.execute(
            """
            SELECT session_id, config_id, status,
                   created_at, updated_at, message_count
            FROM sessions
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        rows = await cursor.fetchall()

        return [
            {
                "session_id": row["session_id"],
                "config_id": row["config_id"],
                "status": row["status"],
                "created_at": datetime.fromisoformat(row["created_at"]),
                "updated_at": datetime.fromisoformat(row["updated_at"]),
                "message_count": row["message_count"],
            }
            for row in rows
        ]

    async def update_session(
        self,
        session_id: str,
        status: str | None = None,
        transcript: list[dict[str, Any]] | None = None,
        message_count: int | None = None,
    ) -> None:
        """Update session."""
        if not self._connection:
            raise RuntimeError("Database not connected")

        updates = ["updated_at = ?"]
        params: list[Any] = [datetime.now(UTC)]

        if status:
            updates.append("status = ?")
            params.append(status)
        if transcript is not None:
            updates.append("transcript = ?")
            params.append(json.dumps(transcript))
        if message_count is not None:
            updates.append("message_count = ?")
            params.append(message_count)

        params.append(session_id)

        await self._connection.execute(
            f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = ?", tuple(params)
        )
        await self._connection.commit()
        logger.debug(f"Updated session: {session_id}")

    async def delete_session(self, session_id: str) -> None:
        """Delete session."""
        if not self._connection:
            raise RuntimeError("Database not connected")

        await self._connection.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        await self._connection.commit()
        logger.debug(f"Deleted session: {session_id}")

    async def cleanup_old_sessions(self, days: int) -> int:
        """Delete sessions older than specified days."""
        if not self._connection:
            raise RuntimeError("Database not connected")

        cutoff = datetime.now(UTC) - timedelta(days=days)
        cursor = await self._connection.execute(
            "DELETE FROM sessions WHERE updated_at < ?", (cutoff,)
        )
        await self._connection.commit()
        deleted = cursor.rowcount or 0
        logger.info(f"Cleaned up {deleted} old sessions (older than {days} days)")
        return deleted

    # Config operations
    async def create_config(
        self,
        config_id: str,
        name: str,
        yaml_content: str,
        description: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Create a new config."""
        if not self._connection:
            raise RuntimeError("Database not connected")

        now = datetime.now(UTC)
        tags_json = json.dumps(tags or {})

        await self._connection.execute(
            """
            INSERT INTO configs (
                config_id, name, description, yaml_content,
                created_at, updated_at, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (config_id, name, description, yaml_content, now, now, tags_json),
        )
        await self._connection.commit()
        logger.debug(f"Created config: {config_id}")

    async def get_config(self, config_id: str) -> dict[str, Any] | None:
        """Get config by ID."""
        if not self._connection:
            raise RuntimeError("Database not connected")

        cursor = await self._connection.execute(
            "SELECT * FROM configs WHERE config_id = ?", (config_id,)
        )
        row = await cursor.fetchone()

        if row:
            return {
                "config_id": row["config_id"],
                "name": row["name"],
                "description": row["description"],
                "yaml_content": row["yaml_content"],
                "created_at": datetime.fromisoformat(row["created_at"]),
                "updated_at": datetime.fromisoformat(row["updated_at"]),
                "tags": json.loads(row["tags"]) if row["tags"] else {},
            }
        return None

    async def update_config(self, config_id: str, **kwargs) -> None:
        """Update config fields."""
        if not self._connection:
            raise RuntimeError("Database not connected")

        updates = ["updated_at = ?"]
        params: list[Any] = [datetime.now(UTC)]

        for key, value in kwargs.items():
            if key == "tags":
                updates.append(f"{key} = ?")
                params.append(json.dumps(value))
            else:
                updates.append(f"{key} = ?")
                params.append(value)

        params.append(config_id)

        await self._connection.execute(
            f"UPDATE configs SET {', '.join(updates)} WHERE config_id = ?", tuple(params)
        )
        await self._connection.commit()
        logger.debug(f"Updated config: {config_id}")

    async def delete_config(self, config_id: str) -> None:
        """Delete config."""
        if not self._connection:
            raise RuntimeError("Database not connected")

        await self._connection.execute("DELETE FROM configs WHERE config_id = ?", (config_id,))
        await self._connection.commit()
        logger.debug(f"Deleted config: {config_id}")

    async def list_configs(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """List all configs."""
        if not self._connection:
            raise RuntimeError("Database not connected")

        cursor = await self._connection.execute(
            """
            SELECT config_id, name, description, created_at, updated_at, tags
            FROM configs
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        rows = await cursor.fetchall()

        return [
            {
                "config_id": row["config_id"],
                "name": row["name"],
                "description": row["description"],
                "created_at": datetime.fromisoformat(row["created_at"]),
                "updated_at": datetime.fromisoformat(row["updated_at"]),
                "tags": json.loads(row["tags"]) if row["tags"] else {},
            }
            for row in rows
        ]

    async def count_configs(self) -> int:
        """Count total configs."""
        if not self._connection:
            raise RuntimeError("Database not connected")

        cursor = await self._connection.execute("SELECT COUNT(*) as count FROM configs")
        row = await cursor.fetchone()
        return row["count"] if row else 0

    # App-level settings operations (key-value pairs)
    async def get_setting(self, key: str) -> Any | None:
        """Get app-level setting value."""
        if not self._connection:
            raise RuntimeError("Database not connected")

        cursor = await self._connection.execute(
            "SELECT value FROM configuration WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return json.loads(row["value"]) if row else None

    async def set_setting(self, key: str, value: Any, scope: str = "global") -> None:
        """Set app-level setting value."""
        if not self._connection:
            raise RuntimeError("Database not connected")

        await self._connection.execute(
            """
            INSERT INTO configuration (key, value, scope, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                scope = excluded.scope,
                updated_at = excluded.updated_at
            """,
            (key, json.dumps(value), scope, datetime.now(UTC)),
        )
        await self._connection.commit()
        logger.debug(f"Set setting: {key}")

    async def get_all_settings(self) -> dict[str, Any]:
        """Get all app-level settings."""
        if not self._connection:
            raise RuntimeError("Database not connected")

        cursor = await self._connection.execute("SELECT key, value FROM configuration")
        rows = await cursor.fetchall()
        return {row["key"]: json.loads(row["value"]) for row in rows}


# Global database instance
_db: Database | None = None


async def init_database() -> Database:
    """Initialize and return global database instance."""
    global _db
    if _db is None:
        db_url = settings.database_url
        # Extract path from sqlite URL
        if db_url.startswith("sqlite+aiosqlite:///"):
            db_path = db_url.replace("sqlite+aiosqlite:///", "")
        else:
            db_path = "./amplifier.db"

        _db = Database(db_path)
        await _db.connect()

    return _db


async def get_db() -> Database:
    """Get database instance (dependency injection).

    Auto-initializes if not already initialized (useful for tests).
    """
    global _db
    if _db is None:
        _db = await init_database()
    return _db
