"""Tests for database layer."""

import tempfile
from datetime import UTC, datetime, timedelta

import pytest

from amplifier_app_api.storage.database import Database


@pytest.mark.asyncio
class TestDatabaseConnection:
    """Test database connection and initialization."""

    async def test_database_connect(self):
        """Test database connection."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db = Database(tmp.name)
            await db.connect()
            assert db._connection is not None
            await db.disconnect()

    async def test_database_disconnect(self):
        """Test database disconnection."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db = Database(tmp.name)
            await db.connect()
            await db.disconnect()
            assert db._connection is None

    async def test_database_schema_initialization(self):
        """Test that schema is created on connect."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db = Database(tmp.name)
            await db.connect()

            # Check tables exist
            if db._connection:
                cursor = await db._connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                tables = await cursor.fetchall()
                table_names = [t[0] for t in tables]

                assert "sessions" in table_names
                assert "configuration" in table_names

            await db.disconnect()


@pytest.mark.asyncio
class TestSessionOperations:
    """Test session database operations."""

    async def test_create_session(self):
        """Test creating a session in database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db = Database(tmp.name)
            await db.connect()

            await db.create_session(
                session_id="test-123",
                status="active",
                bundle="foundation",
                provider="anthropic",
            )

            # Verify it exists
            session = await db.get_session("test-123")
            assert session is not None
            assert session["session_id"] == "test-123"
            assert session["bundle"] == "foundation"

            await db.disconnect()

    async def test_get_nonexistent_session(self):
        """Test getting session that doesn't exist."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db = Database(tmp.name)
            await db.connect()

            session = await db.get_session("nonexistent")
            assert session is None

            await db.disconnect()

    async def test_update_session(self):
        """Test updating session data."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db = Database(tmp.name)
            await db.connect()

            # Create session
            await db.create_session(session_id="test-123", status="active")

            # Update it
            await db.update_session(
                session_id="test-123",
                status="completed",
                message_count=5,
            )

            # Verify update
            session = await db.get_session("test-123")
            assert session is not None
            assert session["status"] == "completed"
            assert session["message_count"] == 5

            await db.disconnect()

    async def test_delete_session(self):
        """Test deleting a session."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db = Database(tmp.name)
            await db.connect()

            # Create and delete
            await db.create_session(session_id="test-123", status="active")
            await db.delete_session("test-123")

            # Verify deleted
            session = await db.get_session("test-123")
            assert session is None

            await db.disconnect()

    async def test_list_sessions(self):
        """Test listing sessions."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db = Database(tmp.name)
            await db.connect()

            # Create multiple sessions
            for i in range(5):
                await db.create_session(session_id=f"test-{i}", status="active")

            # List them
            sessions = await db.list_sessions(limit=10, offset=0)
            assert len(sessions) == 5

            await db.disconnect()

    async def test_list_sessions_with_pagination(self):
        """Test session listing pagination."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db = Database(tmp.name)
            await db.connect()

            # Create 10 sessions
            for i in range(10):
                await db.create_session(session_id=f"test-{i}", status="active")

            # Get first 5
            page1 = await db.list_sessions(limit=5, offset=0)
            assert len(page1) == 5

            # Get next 5
            page2 = await db.list_sessions(limit=5, offset=5)
            assert len(page2) == 5

            # Should be different sessions
            ids1 = [s["session_id"] for s in page1]
            ids2 = [s["session_id"] for s in page2]
            assert set(ids1).isdisjoint(set(ids2))

            await db.disconnect()

    async def test_cleanup_old_sessions(self):
        """Test cleaning up old sessions."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db = Database(tmp.name)
            await db.connect()

            # Create a session
            await db.create_session(session_id="test-old", status="completed")

            # Manually update timestamp to be old (direct SQL for testing)
            old_date = datetime.now(UTC) - timedelta(days=60)
            conn = db._connection
            assert conn is not None
            await conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (old_date, "test-old"),
            )
            await conn.commit()

            # Cleanup sessions older than 30 days
            deleted = await db.cleanup_old_sessions(days=30)
            assert deleted >= 1

            # Verify it's gone
            session = await db.get_session("test-old")
            assert session is None

            await db.disconnect()


@pytest.mark.asyncio
class TestConfigurationOperations:
    """Test configuration database operations."""

    async def test_set_and_get_config(self):
        """Test setting and getting config values."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db = Database(tmp.name)
            await db.connect()

            # Set config
            await db.set_config("test_key", {"value": "test"})

            # Get config
            value = await db.get_config("test_key")
            assert value == {"value": "test"}

            await db.disconnect()

    async def test_get_nonexistent_config(self):
        """Test getting config that doesn't exist."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db = Database(tmp.name)
            await db.connect()

            value = await db.get_config("nonexistent")
            assert value is None

            await db.disconnect()

    async def test_update_existing_config(self):
        """Test updating existing config value."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db = Database(tmp.name)
            await db.connect()

            # Set initial value
            await db.set_config("test_key", {"value": "initial"})

            # Update it
            await db.set_config("test_key", {"value": "updated"})

            # Verify updated
            value = await db.get_config("test_key")
            assert value == {"value": "updated"}

            await db.disconnect()

    async def test_get_all_config(self):
        """Test getting all configuration."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db = Database(tmp.name)
            await db.connect()

            # Set multiple values
            await db.set_config("key1", {"a": 1})
            await db.set_config("key2", {"b": 2})

            # Get all
            all_config = await db.get_all_config()
            assert "key1" in all_config
            assert "key2" in all_config
            assert all_config["key1"] == {"a": 1}
            assert all_config["key2"] == {"b": 2}

            await db.disconnect()


@pytest.mark.asyncio
class TestDatabaseErrors:
    """Test database error handling."""

    async def test_operation_without_connection(self):
        """Test that operations without connection raise error."""
        db = Database(":memory:")
        # Don't connect

        with pytest.raises(RuntimeError, match="Database not connected"):
            await db.get_session("test")

    async def test_double_connect(self):
        """Test connecting twice is safe."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db = Database(tmp.name)
            await db.connect()
            await db.connect()  # Should be safe
            assert db._connection is not None
            await db.disconnect()

    async def test_double_disconnect(self):
        """Test disconnecting twice is safe."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db = Database(tmp.name)
            await db.connect()
            await db.disconnect()
            await db.disconnect()  # Should be safe
            assert db._connection is None
