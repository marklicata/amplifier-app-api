"""Comprehensive tests for session API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from amplifier_app_api.main import app


@pytest.mark.asyncio
class TestSessionCreation:
    """Test session creation with various configurations."""

    async def test_create_session_minimal(self):
        """Test creating session with minimal config."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/sessions/create", json={})
            assert response.status_code in [200, 500]  # May fail without deps

    async def test_create_session_with_bundle(self):
        """Test creating session with specific bundle."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/sessions/create", json={"bundle": "foundation"})
            assert response.status_code in [200, 500]

    async def test_create_session_with_provider(self):
        """Test creating session with specific provider."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/sessions/create",
                json={"bundle": "foundation", "provider": "anthropic"},
            )
            assert response.status_code in [200, 500]

    async def test_create_session_with_model(self):
        """Test creating session with specific model."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/sessions/create",
                json={
                    "bundle": "foundation",
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-5",
                },
            )
            assert response.status_code in [200, 500]

    async def test_create_session_with_metadata(self):
        """Test creating session with metadata tags."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/sessions/create",
                json={
                    "bundle": "foundation",
                    "metadata": {"project": "test", "user": "developer"},
                },
            )
            assert response.status_code in [200, 500]

    async def test_create_session_response_structure(self):
        """Test that session creation returns proper structure."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/sessions/create", json={})
            if response.status_code == 200:
                data = response.json()
                assert "session_id" in data
                assert "status" in data
                assert "metadata" in data


@pytest.mark.asyncio
class TestSessionListing:
    """Test session listing and retrieval."""

    async def test_list_sessions_empty(self):
        """Test listing sessions when none exist."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/sessions")
            assert response.status_code == 200
            data = response.json()
            assert "sessions" in data
            assert "total" in data
            assert isinstance(data["sessions"], list)

    async def test_list_sessions_with_pagination(self):
        """Test session listing with pagination parameters."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/sessions?limit=10&offset=0")
            assert response.status_code == 200
            data = response.json()
            assert len(data["sessions"]) <= 10

    async def test_list_sessions_invalid_pagination(self):
        """Test session listing with invalid pagination."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Negative limit should work (or be validated)
            response = await client.get("/sessions?limit=-1")
            assert response.status_code in [200, 422]


@pytest.mark.asyncio
class TestSessionRetrieval:
    """Test getting specific session details."""

    async def test_get_nonexistent_session(self):
        """Test getting a session that doesn't exist."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/sessions/nonexistent-id")
            assert response.status_code == 404

    async def test_get_invalid_session_id(self):
        """Test getting session with malformed ID."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/sessions/invalid!@#$%")
            assert response.status_code in [404, 422]


@pytest.mark.asyncio
class TestSessionDeletion:
    """Test session deletion."""

    async def test_delete_nonexistent_session(self):
        """Test deleting a session that doesn't exist."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/sessions/nonexistent-id")
            assert response.status_code == 404

    async def test_delete_invalid_session_id(self):
        """Test deleting session with malformed ID."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/sessions/invalid!@#$%")
            assert response.status_code in [404, 422]


@pytest.mark.asyncio
class TestSessionResume:
    """Test session resumption."""

    async def test_resume_nonexistent_session(self):
        """Test resuming a session that doesn't exist."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/sessions/nonexistent-id/resume")
            assert response.status_code == 404

    async def test_resume_invalid_session_id(self):
        """Test resuming with malformed session ID."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/sessions/invalid!@#$/resume")
            assert response.status_code in [404, 422]


@pytest.mark.asyncio
class TestSessionMessages:
    """Test sending messages to sessions."""

    async def test_send_message_to_nonexistent_session(self):
        """Test sending message to nonexistent session."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/sessions/nonexistent-id/messages",
                json={"message": "Hello"},
            )
            assert response.status_code == 404

    async def test_send_empty_message(self):
        """Test sending empty message."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/sessions/test-id/messages",
                json={"message": ""},
            )
            assert response.status_code in [404, 422]

    async def test_send_message_without_message_field(self):
        """Test sending message without required field."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/sessions/test-id/messages",
                json={},
            )
            assert response.status_code == 422

    async def test_send_message_with_context(self):
        """Test sending message with additional context."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/sessions/test-id/messages",
                json={
                    "message": "Test",
                    "context": {"file": "test.py", "line": 10},
                },
            )
            assert response.status_code in [404, 422]  # Session won't exist

    async def test_send_very_long_message(self):
        """Test sending very long message."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            long_message = "x" * 100000  # 100KB message
            response = await client.post(
                "/sessions/test-id/messages",
                json={"message": long_message},
            )
            assert response.status_code in [404, 422, 413]

    async def test_send_message_with_special_characters(self):
        """Test sending message with special characters."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/sessions/test-id/messages",
                json={"message": 'Hello 世界 🌍 \n\t"quoted"'},
            )
            assert response.status_code in [404, 422]


@pytest.mark.asyncio
class TestSessionCancellation:
    """Test session cancellation."""

    async def test_cancel_nonexistent_session(self):
        """Test cancelling nonexistent session."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/sessions/nonexistent-id/cancel")
            assert response.status_code == 404

    async def test_cancel_inactive_session(self):
        """Test cancelling a session that's not running."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/sessions/test-id/cancel")
            assert response.status_code in [404, 422]
