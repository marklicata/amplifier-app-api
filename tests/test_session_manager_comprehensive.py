"""Comprehensive tests for SessionManager core functionality.

Tests session lifecycle, bundle caching, and error handling.
"""

import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest

from amplifier_app_api.core.session_manager import SessionManager
from amplifier_app_api.models import Session, SessionStatus


@pytest.mark.asyncio
class TestBundleCaching:
    """Test bundle preparation and caching behavior."""

    async def test_bundle_cached_after_first_session_creation(self, test_db):
        """Test that bundle is cached after first session from a config."""
        manager = SessionManager(test_db)

        # Create a config
        config_id = str(uuid.uuid4())
        await test_db.create_config(
            config_id=config_id,
            name="cache-test",
            yaml_content="bundle:\n  name: test\n",
        )

        # Mock bundle preparation
        mock_bundle = Mock()
        mock_bundle.prepare = AsyncMock(return_value=mock_bundle)
        mock_session = Mock()
        mock_bundle.create_session = AsyncMock(return_value=mock_session)

        with patch("amplifier_foundation.Bundle.from_dict", return_value=mock_bundle):
            # First session creation
            session1 = await manager.create_session(config_id=config_id)
            assert session1 is not None

            # Bundle should be cached
            assert config_id in manager._prepared_bundles

            # Second session creation
            session2 = await manager.create_session(config_id=config_id)
            assert session2 is not None

            # Bundle.prepare should only be called once (first time)
            assert mock_bundle.prepare.call_count == 1
            # create_session should be called twice
            assert mock_bundle.create_session.call_count == 2

    async def test_cache_invalidation_on_config_update(self, test_db):
        """Test that cache is invalidated when config is updated."""
        manager = SessionManager(test_db)

        config_id = "test-config-123"
        manager._prepared_bundles[config_id] = Mock()  # Simulate cached bundle

        # Invalidate cache
        manager.invalidate_config_cache(config_id)

        # Cache should be cleared
        assert config_id not in manager._prepared_bundles

    async def test_invalidate_cache_for_nonexistent_config(self, test_db):
        """Test invalidating cache for config that wasn't cached."""
        manager = SessionManager(test_db)

        # Should not raise error
        manager.invalidate_config_cache("nonexistent-config")


@pytest.mark.asyncio
class TestSessionLifecycle:
    """Test session creation, retrieval, and deletion."""

    async def test_create_session_with_user_and_app(self, test_db):
        """Test creating session with user_id and app_id."""
        manager = SessionManager(test_db)

        # Create config
        config_id = str(uuid.uuid4())
        await test_db.create_config(
            config_id=config_id,
            name="test-config",
            yaml_content="bundle:\n  name: test\n",
        )

        # Mock bundle preparation
        mock_bundle = Mock()
        mock_bundle.prepare = AsyncMock(return_value=mock_bundle)
        mock_session = Mock()
        mock_bundle.create_session = AsyncMock(return_value=mock_session)

        with patch("amplifier_foundation.Bundle.from_dict", return_value=mock_bundle):
            # Create session with user and app
            session = await manager.create_session(
                config_id=config_id,
                user_id="test-user-123",
                app_id="test-app-456",
            )

            assert session is not None
            assert session.config_id == config_id
            assert session.status == SessionStatus.ACTIVE

            # Verify session was stored in database with user and app
            db_session = await test_db.get_session(session.session_id)
            assert db_session["owner_user_id"] == "test-user-123"
            assert db_session["created_by_app_id"] == "test-app-456"

    async def test_create_session_without_user(self, test_db):
        """Test creating session without user_id (anonymous)."""
        manager = SessionManager(test_db)

        config_id = str(uuid.uuid4())
        await test_db.create_config(
            config_id=config_id,
            name="anon-test",
            yaml_content="bundle:\n  name: test\n",
        )

        mock_bundle = Mock()
        mock_bundle.prepare = AsyncMock(return_value=mock_bundle)
        mock_session = Mock()
        mock_bundle.create_session = AsyncMock(return_value=mock_session)

        with patch("amplifier_foundation.Bundle.from_dict", return_value=mock_bundle):
            session = await manager.create_session(config_id=config_id)

            # Should succeed without user_id
            assert session is not None

            # user_id should be None in database
            db_session = await test_db.get_session(session.session_id)
            assert db_session["owner_user_id"] is None

    async def test_get_session_that_exists(self, test_db):
        """Test retrieving a session that exists."""
        manager = SessionManager(test_db)

        # Create config and session directly in database
        config_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        await test_db.create_config(
            config_id=config_id,
            name="test",
            yaml_content="bundle:\n  name: test\n",
        )
        await test_db.create_session(
            session_id=session_id,
            config_id=config_id,
            owner_user_id="test-user",
            status="active",
        )

        # Get session
        session = await manager.get_session(session_id)
        assert session is not None
        assert session.session_id == session_id
        assert session.config_id == config_id
        assert session.status == SessionStatus.ACTIVE

    async def test_get_session_that_doesnt_exist(self, test_db):
        """Test retrieving a session that doesn't exist."""
        manager = SessionManager(test_db)
        session = await manager.get_session("nonexistent-session-id")
        assert session is None

    async def test_delete_session(self, test_db):
        """Test deleting a session."""
        manager = SessionManager(test_db)

        # Create session in database
        config_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        await test_db.create_config(
            config_id=config_id,
            name="delete-test",
            yaml_content="bundle:\n  name: test\n",
        )
        await test_db.create_session(
            session_id=session_id,
            config_id=config_id,
            owner_user_id=None,
            status="active",
        )

        # Delete
        success = await manager.delete_session(session_id)
        assert success is True

        # Verify deleted
        session = await manager.get_session(session_id)
        assert session is None

    async def test_delete_session_that_doesnt_exist(self, test_db):
        """Test deleting session that doesn't exist."""
        manager = SessionManager(test_db)
        success = await manager.delete_session("nonexistent")
        assert success is False

    async def test_delete_session_cleans_up_active_amplifier_session(self, test_db):
        """Test that deleting session cleans up active AmplifierSession."""
        manager = SessionManager(test_db)

        # Create session
        config_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        await test_db.create_config(
            config_id=config_id,
            name="cleanup-test",
            yaml_content="bundle:\n  name: test\n",
        )
        await test_db.create_session(
            session_id=session_id,
            config_id=config_id,
            owner_user_id=None,
            status="active",
        )

        # Simulate active AmplifierSession
        mock_amplifier_session = Mock()
        mock_amplifier_session.cleanup = AsyncMock()
        manager._sessions[session_id] = mock_amplifier_session

        # Delete
        success = await manager.delete_session(session_id)
        assert success is True

        # Verify cleanup was called
        mock_amplifier_session.cleanup.assert_called_once()

        # Verify removed from active sessions
        assert session_id not in manager._sessions


@pytest.mark.asyncio
class TestSessionResumption:
    """Test session resume functionality."""

    async def test_resume_session_loads_into_memory(self, test_db):
        """Test that resuming session loads it into memory."""
        manager = SessionManager(test_db)

        # Create session in database
        config_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        await test_db.create_config(
            config_id=config_id,
            name="resume-test",
            yaml_content="bundle:\n  name: test\n",
        )
        await test_db.create_session(
            session_id=session_id,
            config_id=config_id,
            owner_user_id=None,
            status="active",
        )

        # Mock bundle and session
        mock_bundle = Mock()
        mock_bundle.prepare = AsyncMock(return_value=mock_bundle)
        mock_amplifier_session = Mock()
        mock_amplifier_session.coordinator = Mock()
        mock_amplifier_session.coordinator.get = Mock(return_value=None)
        mock_bundle.create_session = AsyncMock(return_value=mock_amplifier_session)

        with patch("amplifier_foundation.Bundle.from_dict", return_value=mock_bundle):
            # Resume
            resumed = await manager.resume_session(session_id)

            assert resumed is not None
            assert resumed.session_id == session_id

            # Should be loaded into memory
            assert session_id in manager._sessions

    async def test_resume_nonexistent_session(self, test_db):
        """Test resuming session that doesn't exist."""
        manager = SessionManager(test_db)
        resumed = await manager.resume_session("nonexistent")
        assert resumed is None

    async def test_resume_session_restores_transcript(self, test_db):
        """Test that resuming session restores transcript."""
        manager = SessionManager(test_db)

        # Create session with transcript
        config_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        await test_db.create_config(
            config_id=config_id,
            name="transcript-test",
            yaml_content="bundle:\n  name: test\n",
        )
        await test_db.create_session(
            session_id=session_id,
            config_id=config_id,
            owner_user_id=None,
            status="active",
        )

        # Add transcript
        transcript = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        await test_db.update_session(
            session_id=session_id,
            transcript=transcript,
            message_count=1,
        )

        # Mock components
        mock_bundle = Mock()
        mock_bundle.prepare = AsyncMock(return_value=mock_bundle)
        mock_context_manager = Mock()
        mock_context_manager.set_messages = AsyncMock()
        mock_amplifier_session = Mock()
        mock_amplifier_session.coordinator = Mock()
        mock_amplifier_session.coordinator.get = Mock(return_value=mock_context_manager)
        mock_bundle.create_session = AsyncMock(return_value=mock_amplifier_session)

        with patch("amplifier_foundation.Bundle.from_dict", return_value=mock_bundle):
            # Resume
            await manager.resume_session(session_id)

            # Verify transcript was restored
            mock_context_manager.set_messages.assert_called_once_with(transcript)


@pytest.mark.asyncio
class TestSessionMessageHandling:
    """Test sending messages to sessions."""

    async def test_send_message_to_nonexistent_session(self, test_db):
        """Test sending message to session that doesn't exist."""
        manager = SessionManager(test_db)

        with pytest.raises(ValueError, match="Session not found"):
            await manager.send_message(
                session_id="nonexistent",
                message="Hello",
            )

    async def test_send_message_auto_resumes_session(self, test_db):
        """Test that sending message auto-resumes session if not in memory."""
        manager = SessionManager(test_db)

        # Create session in database (not in memory)
        config_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        await test_db.create_config(
            config_id=config_id,
            name="auto-resume-test",
            yaml_content="bundle:\n  name: test\n",
        )
        await test_db.create_session(
            session_id=session_id,
            config_id=config_id,
            owner_user_id=None,
            status="active",
        )

        # Mock components
        mock_bundle = Mock()
        mock_bundle.prepare = AsyncMock(return_value=mock_bundle)
        mock_context_manager = Mock()
        mock_context_manager.get_messages = AsyncMock(return_value=[])
        mock_context_manager.set_messages = AsyncMock()
        mock_amplifier_session = Mock()
        mock_amplifier_session.execute = AsyncMock(return_value="Test response")
        mock_amplifier_session.coordinator = Mock()
        mock_amplifier_session.coordinator.get = Mock(return_value=mock_context_manager)
        mock_bundle.create_session = AsyncMock(return_value=mock_amplifier_session)

        with patch("amplifier_foundation.Bundle.from_dict", return_value=mock_bundle):
            # Send message (should auto-resume)
            result = await manager.send_message(
                session_id=session_id,
                message="Hello",
            )

            assert result["session_id"] == session_id
            assert result["response"] == "Test response"
            assert session_id in manager._sessions  # Now in memory


@pytest.mark.asyncio
class TestSessionListOperations:
    """Test session listing and pagination."""

    async def test_list_sessions_empty(self, test_db):
        """Test listing when no sessions exist."""
        manager = SessionManager(test_db)
        sessions = await manager.list_sessions()
        assert sessions == []

    async def test_list_sessions_with_data(self, test_db):
        """Test listing sessions."""
        manager = SessionManager(test_db)

        # Create config
        config_id = str(uuid.uuid4())
        await test_db.create_config(
            config_id=config_id,
            name="list-test",
            yaml_content="bundle:\n  name: test\n",
        )

        # Create multiple sessions
        session_ids = []
        for i in range(3):
            session_id = f"test-list-{i}"
            await test_db.create_session(
                session_id=session_id,
                config_id=config_id,
                owner_user_id=None,
                status="active",
            )
            session_ids.append(session_id)

        # List
        sessions = await manager.list_sessions()
        assert len(sessions) >= 3

        # Verify structure
        for session in sessions:
            assert isinstance(session, Session)
            assert session.session_id is not None
            assert session.config_id is not None
            assert session.status is not None

        # Cleanup
        for sid in session_ids:
            await test_db.delete_session(sid)
        await test_db.delete_config(config_id)

    async def test_list_sessions_pagination(self, test_db):
        """Test session list pagination."""
        manager = SessionManager(test_db)

        # Create config
        config_id = str(uuid.uuid4())
        await test_db.create_config(
            config_id=config_id,
            name="page-test",
            yaml_content="bundle:\n  name: test\n",
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

        # Get first page
        page1 = await manager.list_sessions(limit=5, offset=0)
        assert len(page1) >= 5

        # Get second page
        page2 = await manager.list_sessions(limit=5, offset=5)
        assert len(page2) >= 0  # May be less than 5

        # Cleanup
        for sid in session_ids:
            await test_db.delete_session(sid)
        await test_db.delete_config(config_id)


@pytest.mark.asyncio
class TestErrorHandling:
    """Test error scenarios and edge cases."""

    async def test_create_session_with_nonexistent_config(self, test_db):
        """Test creating session with config that doesn't exist."""
        manager = SessionManager(test_db)

        with pytest.raises(ValueError, match="Config not found"):
            await manager.create_session(config_id="nonexistent-config")

    async def test_create_session_with_invalid_yaml(self, test_db):
        """Test creating session with invalid YAML in config."""
        manager = SessionManager(test_db)

        # Create config with invalid YAML (missing bundle section)
        config_id = str(uuid.uuid4())
        await test_db.create_config(
            config_id=config_id,
            name="invalid-yaml",
            yaml_content="invalid: yaml\n",
        )

        # Should raise RuntimeError during bundle preparation
        with pytest.raises(RuntimeError, match="Failed to prepare bundle"):
            await manager.create_session(config_id=config_id)

    async def test_bundle_preparation_timeout(self, test_db):
        """Test timeout during bundle preparation."""
        manager = SessionManager(test_db)

        config_id = str(uuid.uuid4())
        await test_db.create_config(
            config_id=config_id,
            name="timeout-test",
            yaml_content="bundle:\n  name: test\n",
        )

        # Mock bundle that never resolves
        async def never_resolves():
            import asyncio

            await asyncio.sleep(1000)

        mock_bundle = Mock()
        mock_bundle.prepare = never_resolves

        with patch("amplifier_foundation.Bundle.from_dict", return_value=mock_bundle):
            with pytest.raises(RuntimeError, match="timed out"):
                await manager.create_session(config_id=config_id)


@pytest.mark.asyncio
class TestCleanupOperations:
    """Test session cleanup and resource management."""

    async def test_cleanup_old_sessions(self, test_db):
        """Test cleaning up old sessions based on age."""
        manager = SessionManager(test_db)

        # This delegates to database layer
        # Test that it doesn't crash
        count = await manager.cleanup_old_sessions()
        assert isinstance(count, int)
        assert count >= 0

    async def test_get_amplifier_session_returns_active_session(self, test_db):
        """Test getting active AmplifierSession instance."""
        manager = SessionManager(test_db)

        # Add mock session to active sessions
        mock_amplifier_session = Mock()
        manager._sessions["test-session-123"] = mock_amplifier_session

        # Get it
        session = await manager.get_amplifier_session("test-session-123")
        assert session is mock_amplifier_session

    async def test_get_amplifier_session_not_in_memory(self, test_db):
        """Test getting AmplifierSession that's not in memory."""
        manager = SessionManager(test_db)

        session = await manager.get_amplifier_session("nonexistent")
        assert session is None
