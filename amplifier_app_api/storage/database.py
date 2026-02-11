"""Database management with PostgreSQL via asyncpg."""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from ..config import settings

logger = logging.getLogger(__name__)


class Database:
    """Async PostgreSQL database manager using asyncpg."""

    def __init__(self, db_url: str):
        """Initialize database with connection URL."""
        self.db_url = db_url
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        """Establish database connection pool and initialize schema."""
        if self._pool is not None:
            return

        # Create connection pool
        self._pool = await asyncpg.create_pool(
            self.db_url,
            min_size=settings.database_pool_min_size,
            max_size=settings.database_pool_max_size,
            command_timeout=60,
        )

        # Initialize schema
        from .schema import INIT_SCHEMA

        async with self._pool.acquire() as conn:
            await conn.execute(INIT_SCHEMA)

        logger.info(f"Database connected: {self.db_url.split('@')[-1]}")  # Don't log password

    async def disconnect(self) -> None:
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Database disconnected")

    # Session operations
    async def create_session(
        self,
        session_id: str,
        config_id: str,
        owner_user_id: str | None,
        status: str,
        created_by_app_id: str | None = None,
    ) -> None:
        """Create a new session with owner user."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Create session
                await conn.execute(
                    """
                    INSERT INTO sessions (
                        session_id, config_id, owner_user_id,
                        created_by_app_id, status, message_count, transcript
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                    """,
                    session_id,
                    config_id,
                    owner_user_id,
                    created_by_app_id,
                    status,
                    0,
                    json.dumps([]),  # Convert list to JSON string for JSONB
                )

                # Add owner as participant if user_id provided
                if owner_user_id:
                    await conn.execute(
                        """
                        INSERT INTO session_participants (session_id, user_id, role)
                        VALUES ($1, $2, $3)
                        """,
                        session_id,
                        owner_user_id,
                        "owner",
                    )

        logger.debug(f"Created session: {session_id}")

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session by ID."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM sessions WHERE session_id = $1", session_id)

        if row:
            return {
                "session_id": row["session_id"],
                "config_id": row["config_id"],
                "owner_user_id": row["owner_user_id"],
                "created_by_app_id": row["created_by_app_id"],
                "last_accessed_by_app_id": row["last_accessed_by_app_id"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "last_accessed_at": row["last_accessed_at"],
                "message_count": row["message_count"],
                "transcript": json.loads(row["transcript"])
                if isinstance(row["transcript"], str)
                else row["transcript"],
                "metadata": json.loads(row["metadata"])
                if isinstance(row["metadata"], str)
                else row["metadata"],
            }
        return None

    async def list_sessions(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """List all sessions."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT session_id, config_id, owner_user_id, status,
                       created_at, updated_at, message_count
                FROM sessions
                ORDER BY updated_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )

        return [
            {
                "session_id": row["session_id"],
                "config_id": row["config_id"],
                "owner_user_id": row["owner_user_id"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
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
        if not self._pool:
            raise RuntimeError("Database not connected")

        updates = ["updated_at = NOW()"]
        params: list[Any] = []
        param_idx = 1

        if status:
            updates.append(f"status = ${param_idx}")
            params.append(status)
            param_idx += 1
        if transcript is not None:
            updates.append(f"transcript = ${param_idx}::jsonb")
            params.append(json.dumps(transcript))  # Convert to JSON string for JSONB
            param_idx += 1
        if message_count is not None:
            updates.append(f"message_count = ${param_idx}")
            params.append(message_count)
            param_idx += 1

        params.append(session_id)

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = ${param_idx}",
                *params,
            )

        logger.debug(f"Updated session: {session_id}")

    async def delete_session(self, session_id: str) -> None:
        """Delete session."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM sessions WHERE session_id = $1", session_id)

        logger.debug(f"Deleted session: {session_id}")

    async def cleanup_old_sessions(self, days: int) -> int:
        """Delete sessions older than specified days."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        cutoff = datetime.now(UTC) - timedelta(days=days)

        async with self._pool.acquire() as conn:
            result = await conn.execute("DELETE FROM sessions WHERE updated_at < $1", cutoff)

        # Extract count from result string "DELETE N"
        deleted = int(result.split()[-1]) if result else 0
        logger.info(f"Cleaned up {deleted} old sessions (older than {days} days)")
        return deleted

    # Session participants operations
    async def add_session_participant(
        self, session_id: str, user_id: str, role: str = "viewer"
    ) -> None:
        """Add a user to a session with specified role."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO session_participants (session_id, user_id, role)
                VALUES ($1, $2, $3)
                ON CONFLICT (session_id, user_id) DO UPDATE
                SET last_active_at = NOW()
                """,
                session_id,
                user_id,
                role,
            )

        logger.debug(f"Added participant {user_id} to session {session_id}")

    async def remove_session_participant(self, session_id: str, user_id: str) -> None:
        """Remove a user from a session."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM session_participants WHERE session_id = $1 AND user_id = $2",
                session_id,
                user_id,
            )

        logger.debug(f"Removed participant {user_id} from session {session_id}")

    async def get_session_participants(self, session_id: str) -> list[dict[str, Any]]:
        """Get all participants for a session."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, role, joined_at, last_active_at, permissions
                FROM session_participants
                WHERE session_id = $1
                ORDER BY joined_at
                """,
                session_id,
            )

        return [dict(row) for row in rows]

    async def get_user_sessions(self, user_id: str) -> list[dict[str, Any]]:
        """Get all sessions a user participates in."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT s.*, sp.role, sp.joined_at, sp.last_active_at
                FROM sessions s
                JOIN session_participants sp ON s.session_id = sp.session_id
                WHERE sp.user_id = $1
                ORDER BY sp.last_active_at DESC NULLS LAST
                """,
                user_id,
            )

        return [dict(row) for row in rows]

    async def update_participant_role(self, session_id: str, user_id: str, role: str) -> None:
        """Update a participant's role."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE session_participants
                SET role = $1, last_active_at = NOW()
                WHERE session_id = $2 AND user_id = $3
                """,
                role,
                session_id,
                user_id,
            )

        logger.debug(f"Updated participant {user_id} role to {role} in session {session_id}")

    # Config operations
    async def create_config(
        self,
        config_id: str,
        name: str,
        config_json: str,
        description: str | None = None,
        tags: dict[str, str] | None = None,
        user_id: str | None = None,
    ) -> None:
        """Create a new config."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO configs (
                    config_id, name, description, config_json, user_id, tags
                )
                VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                """,
                config_id,
                name,
                description,
                config_json,
                user_id,
                json.dumps(tags or {}),  # Convert dict to JSON string for JSONB
            )

        logger.debug(f"Created config: {config_id}")

    async def get_config(self, config_id: str) -> dict[str, Any] | None:
        """Get config by ID."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM configs WHERE config_id = $1", config_id)

        if row:
            return {
                "config_id": row["config_id"],
                "name": row["name"],
                "description": row["description"],
                "config_json": row["config_json"],
                "user_id": row["user_id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "tags": json.loads(row["tags"]) if isinstance(row["tags"], str) else row["tags"],
            }
        return None

    async def update_config(self, config_id: str, **kwargs) -> None:
        """Update config fields."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        updates = ["updated_at = NOW()"]
        params: list[Any] = []
        param_idx = 1

        for key, value in kwargs.items():
            if key in ("tags", "config_json"):
                # config_json is already a JSON string, but we need to cast it to jsonb
                updates.append(f"{key} = ${param_idx}::jsonb")
                params.append(json.dumps(value) if key == "tags" else value)
            else:
                updates.append(f"{key} = ${param_idx}")
                params.append(value)
            param_idx += 1

        params.append(config_id)

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"UPDATE configs SET {', '.join(updates)} WHERE config_id = ${param_idx}",
                *params,
            )

        logger.debug(f"Updated config: {config_id}")

    async def delete_config(self, config_id: str) -> None:
        """Delete config."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM configs WHERE config_id = $1", config_id)

        logger.debug(f"Deleted config: {config_id}")

    async def list_configs(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """List all configs."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT config_id, name, description, user_id, created_at, updated_at, tags
                FROM configs
                ORDER BY updated_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )

        return [
            {
                "config_id": row["config_id"],
                "name": row["name"],
                "description": row["description"],
                "user_id": row["user_id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "tags": json.loads(row["tags"]) if isinstance(row["tags"], str) else row["tags"],
            }
            for row in rows
        ]

    async def count_configs(self) -> int:
        """Count total configs."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM configs")

        return count or 0

    # App-level settings operations (key-value pairs)
    async def get_setting(self, key: str) -> Any | None:
        """Get app-level setting value."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            value = await conn.fetchval("SELECT value FROM configuration WHERE key = $1", key)

        if value:
            return json.loads(value) if isinstance(value, str) else value
        return None

    async def set_setting(self, key: str, value: Any, scope: str = "global") -> None:
        """Set app-level setting value."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO configuration (key, value, scope)
                VALUES ($1, $2::jsonb, $3)
                ON CONFLICT(key) DO UPDATE SET
                    value = EXCLUDED.value,
                    scope = EXCLUDED.scope,
                    updated_at = NOW()
                """,
                key,
                json.dumps(value),  # Convert to JSON string for JSONB
                scope,
            )

        logger.debug(f"Set setting: {key}")

    async def get_all_settings(self) -> dict[str, Any]:
        """Get all app-level settings."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT key, value FROM configuration")

        return {
            row["key"]: json.loads(row["value"]) if isinstance(row["value"], str) else row["value"]
            for row in rows
        }

    # Recipe operations
    async def create_recipe(
        self,
        recipe_id: str,
        user_id: str,
        name: str,
        recipe_json: str,
        description: str | None = None,
        version: str = "1.0.0",
        tags: dict[str, str] | None = None,
    ) -> None:
        """Create a new recipe."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO recipes (
                    recipe_id, user_id, name, description, version, recipe_data, tags
                )
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb)
                """,
                recipe_id,
                user_id,
                name,
                description,
                version,
                recipe_json,
                json.dumps(tags or {}),
            )

        logger.debug(f"Created recipe: {recipe_id}")

    async def get_recipe(self, recipe_id: str, user_id: str) -> dict[str, Any] | None:
        """Get recipe by ID for a specific user."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM recipes WHERE recipe_id = $1 AND user_id = $2", recipe_id, user_id
            )

        if row:
            return {
                "recipe_id": str(row["recipe_id"]),
                "user_id": row["user_id"],
                "name": row["name"],
                "description": row["description"],
                "version": row["version"],
                "recipe_data": json.loads(row["recipe_data"])
                if isinstance(row["recipe_data"], str)
                else row["recipe_data"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "tags": json.loads(row["tags"]) if isinstance(row["tags"], str) else row["tags"],
            }
        return None

    async def update_recipe(self, recipe_id: str, user_id: str, **kwargs) -> None:
        """Update recipe fields."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        updates = ["updated_at = NOW()"]
        params: list[Any] = []
        param_idx = 1

        for key, value in kwargs.items():
            if key in ("tags", "recipe_data"):
                updates.append(f"{key} = ${param_idx}::jsonb")
                params.append(json.dumps(value) if key == "tags" else value)
            else:
                updates.append(f"{key} = ${param_idx}")
                params.append(value)
            param_idx += 1

        params.extend([recipe_id, user_id])

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"UPDATE recipes SET {', '.join(updates)} WHERE recipe_id = ${param_idx} AND user_id = ${param_idx + 1}",
                *params,
            )

        logger.debug(f"Updated recipe: {recipe_id}")

    async def delete_recipe(self, recipe_id: str, user_id: str) -> bool:
        """Delete recipe."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM recipes WHERE recipe_id = $1 AND user_id = $2", recipe_id, user_id
            )

        deleted = result.split()[-1] != "0" if result else False
        if deleted:
            logger.debug(f"Deleted recipe: {recipe_id}")
        return deleted

    async def list_recipes(
        self, user_id: str, tag_filters: dict[str, str] | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """List all recipes for a user."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        query = """
            SELECT recipe_id, user_id, name, description, version, created_at, updated_at, tags
            FROM recipes
            WHERE user_id = $1
        """
        params: list[Any] = [user_id]

        # Add tag filtering if provided
        if tag_filters:
            for key, value in tag_filters.items():
                query += f" AND tags->>${len(params)} = ${len(params) + 1}"
                params.extend([key, value])

        query += f" ORDER BY updated_at DESC LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}"
        params.extend([limit, offset])

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [
            {
                "recipe_id": str(row["recipe_id"]),
                "user_id": row["user_id"],
                "name": row["name"],
                "description": row["description"],
                "version": row["version"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "tags": json.loads(row["tags"]) if isinstance(row["tags"], str) else row["tags"],
            }
            for row in rows
        ]

    async def count_recipes(self, user_id: str) -> int:
        """Count total recipes for a user."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM recipes WHERE user_id = $1", user_id)

        return count or 0


# Global database instance
_db: Database | None = None


async def init_database() -> Database:
    """Initialize and return global database instance."""
    global _db
    if _db is None:
        db_url = settings.get_database_url()
        _db = Database(db_url)
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
