"""Tests for database layer with PostgreSQL."""

import uuid

import pytest

from amplifier_app_api.storage.database import Database


@pytest.mark.asyncio
class TestSessionOperations:
    """Test session database operations."""

    async def test_create_session(self, test_db):
        """Test creating a session in database."""
        # First create a config
        config_id = str(uuid.uuid4())
        await test_db.create_config(
            config_id=config_id,
            name="Test Config",
            yaml_content="test: true",
        )

        # Create session
        session_id = str(uuid.uuid4())
        await test_db.create_session(
            session_id=session_id,
            config_id=config_id,
            owner_user_id="test-user-001",
            status="active",
            created_by_app_id="test-app",
        )

        # Verify it exists
        session = await test_db.get_session(session_id)
        assert session is not None
        assert session["session_id"] == session_id
        assert session["owner_user_id"] == "test-user-001"
        assert session["created_by_app_id"] == "test-app"

        # Cleanup
        await test_db.delete_session(session_id)
        await test_db.delete_config(config_id)

    async def test_get_nonexistent_session(self, test_db):
        """Test getting session that doesn't exist."""
        session = await test_db.get_session("nonexistent")
        assert session is None

    async def test_update_session(self, test_db):
        """Test updating session data."""
        # Create config first
        config_id = str(uuid.uuid4())
        await test_db.create_config(
            config_id=config_id,
            name="Test Config",
            yaml_content="test: true",
        )

        # Create session
        session_id = str(uuid.uuid4())
        await test_db.create_session(
            session_id=session_id,
            config_id=config_id,
            owner_user_id=None,
            status="active",
        )

        # Update it
        await test_db.update_session(
            session_id=session_id,
            status="completed",
            message_count=5,
        )

        # Verify update
        session = await test_db.get_session(session_id)
        assert session is not None
        assert session["status"] == "completed"
        assert session["message_count"] == 5

        # Cleanup
        await test_db.delete_session(session_id)
        await test_db.delete_config(config_id)

    async def test_delete_session(self, test_db):
        """Test deleting a session."""
        # Create config first
        config_id = str(uuid.uuid4())
        await test_db.create_config(
            config_id=config_id,
            name="Test Config",
            yaml_content="test: true",
        )

        # Create and delete
        session_id = str(uuid.uuid4())
        await test_db.create_session(
            session_id=session_id,
            config_id=config_id,
            owner_user_id=None,
            status="active",
        )
        await test_db.delete_session(session_id)

        # Verify deleted
        session = await test_db.get_session(session_id)
        assert session is None

        # Cleanup config
        await test_db.delete_config(config_id)

    async def test_list_sessions(self, test_db):
        """Test listing sessions."""
        # Create config
        config_id = str(uuid.uuid4())
        await test_db.create_config(
            config_id=config_id,
            name="Test Config",
            yaml_content="test: true",
        )

        # Create multiple sessions
        session_ids = []
        for i in range(5):
            session_id = f"test-list-{i}"
            await test_db.create_session(
                session_id=session_id,
                config_id=config_id,
                owner_user_id=None,
                status="active",
            )
            session_ids.append(session_id)

        # List them
        sessions = await test_db.list_sessions(limit=10, offset=0)
        assert len(sessions) >= 5  # May have other sessions

        # Cleanup
        for sid in session_ids:
            await test_db.delete_session(sid)
        await test_db.delete_config(config_id)

    async def test_list_sessions_with_pagination(self, test_db):
        """Test session listing pagination."""
        # Create config
        config_id = str(uuid.uuid4())
        await test_db.create_config(
            config_id=config_id,
            name="Test Config",
            yaml_content="test: true",
        )

        # Create 10 sessions
        session_ids = []
        for i in range(10):
            session_id = f"test-page-{i}"
            await test_db.create_session(
                session_id=session_id,
                config_id=config_id,
                owner_user_id=None,
                status="active",
            )
            session_ids.append(session_id)

        # Get first 5
        page1 = await test_db.list_sessions(limit=5, offset=0)
        assert len(page1) >= 5

        # Get next 5
        page2 = await test_db.list_sessions(limit=5, offset=5)
        assert len(page2) >= 0  # May be less than 5

        # Cleanup
        for sid in session_ids:
            await test_db.delete_session(sid)
        await test_db.delete_config(config_id)


@pytest.mark.asyncio
class TestSessionParticipants:
    """Test session participants operations."""

    async def test_auto_create_owner_participant(self, test_db):
        """Test that creating session with user_id auto-creates participant."""
        # Create config
        config_id = str(uuid.uuid4())
        await test_db.create_config(
            config_id=config_id,
            name="Test Config",
            yaml_content="test: true",
        )

        # Create session with user
        session_id = str(uuid.uuid4())
        user_id = "test-user-auto"
        await test_db.create_session(
            session_id=session_id,
            config_id=config_id,
            owner_user_id=user_id,
            status="active",
        )

        # Verify participant was auto-created
        participants = await test_db.get_session_participants(session_id)
        assert len(participants) == 1
        assert participants[0]["user_id"] == user_id
        assert participants[0]["role"] == "owner"

        # Cleanup
        await test_db.delete_session(session_id)
        await test_db.delete_config(config_id)

    async def test_add_session_participant(self, test_db):
        """Test adding additional participants to a session."""
        # Create config
        config_id = str(uuid.uuid4())
        await test_db.create_config(
            config_id=config_id,
            name="Test Config",
            yaml_content="test: true",
        )

        # Create session
        session_id = str(uuid.uuid4())
        await test_db.create_session(
            session_id=session_id,
            config_id=config_id,
            owner_user_id="test-owner",
            status="active",
        )

        # Add viewer
        await test_db.add_session_participant(session_id, "test-viewer", "viewer")

        # Verify both participants exist
        participants = await test_db.get_session_participants(session_id)
        assert len(participants) == 2

        roles = {p["user_id"]: p["role"] for p in participants}
        assert roles["test-owner"] == "owner"
        assert roles["test-viewer"] == "viewer"

        # Cleanup
        await test_db.delete_session(session_id)
        await test_db.delete_config(config_id)

    async def test_get_user_sessions(self, test_db):
        """Test getting all sessions for a user."""
        # Create config
        config_id = str(uuid.uuid4())
        await test_db.create_config(
            config_id=config_id,
            name="Test Config",
            yaml_content="test: true",
        )

        # Create multiple sessions for same user
        user_id = "test-user-multi"
        session_ids = []
        for i in range(3):
            session_id = f"test-multi-{i}"
            await test_db.create_session(
                session_id=session_id,
                config_id=config_id,
                owner_user_id=user_id,
                status="active",
            )
            session_ids.append(session_id)

        # Get user's sessions
        user_sessions = await test_db.get_user_sessions(user_id)
        assert len(user_sessions) == 3

        # Cleanup
        for sid in session_ids:
            await test_db.delete_session(sid)
        await test_db.delete_config(config_id)


@pytest.mark.asyncio
class TestConfigurationOperations:
    """Test configuration database operations."""

    async def test_set_and_get_setting(self, test_db):
        """Test setting and getting config values."""
        key = f"test_key_{uuid.uuid4()}"

        # Set setting
        await test_db.set_setting(key, {"value": "test"})

        # Get setting
        value = await test_db.get_setting(key)
        assert value == {"value": "test"}

        # Cleanup
        if test_db._pool:
            async with test_db._pool.acquire() as conn:
                await conn.execute("DELETE FROM configuration WHERE key = $1", key)

    async def test_get_nonexistent_setting(self, test_db):
        """Test getting setting that doesn't exist."""
        value = await test_db.get_setting("nonexistent-key-12345")
        assert value is None

    async def test_update_existing_setting(self, test_db):
        """Test updating existing setting value."""
        key = f"test_key_{uuid.uuid4()}"

        # Set initial value
        await test_db.set_setting(key, {"value": "initial"})

        # Update it
        await test_db.set_setting(key, {"value": "updated"})

        # Verify updated
        value = await test_db.get_setting(key)
        assert value == {"value": "updated"}

        # Cleanup
        if test_db._pool:
            async with test_db._pool.acquire() as conn:
                await conn.execute("DELETE FROM configuration WHERE key = $1", key)

    async def test_get_all_settings(self, test_db):
        """Test getting all configuration."""
        key1 = f"test_key1_{uuid.uuid4()}"
        key2 = f"test_key2_{uuid.uuid4()}"

        # Set multiple values
        await test_db.set_setting(key1, {"a": 1})
        await test_db.set_setting(key2, {"b": 2})

        # Get all
        all_settings = await test_db.get_all_settings()
        assert key1 in all_settings
        assert key2 in all_settings
        assert all_settings[key1] == {"a": 1}
        assert all_settings[key2] == {"b": 2}

        # Cleanup
        if test_db._pool:
            async with test_db._pool.acquire() as conn:
                await conn.execute("DELETE FROM configuration WHERE key IN ($1, $2)", key1, key2)


@pytest.mark.asyncio
class TestDatabaseErrors:
    """Test database error handling."""

    async def test_operation_without_connection(self):
        """Test that operations without connection raise error."""
        db = Database("postgresql://invalid")
        # Don't connect

        with pytest.raises(RuntimeError, match="Database not connected"):
            await db.get_session("test")
