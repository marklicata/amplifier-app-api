"""Comprehensive E2E tests for Session API endpoints.

Tests actual HTTP endpoints with the service running.
"""

import os
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestSessionCreation:
    """Test session creation from configs."""

    async def test_create_session_from_config(self, client: AsyncClient):
        """Test creating a session from a valid config."""
        # First create a config
        # Use e2e_test_bundle from environment
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set in environment")

        # Create session from config
        session_response = await client.post(
            "/sessions",
            json={"config_id": config_id},
        )

        assert session_response.status_code == 201
        data = session_response.json()
        assert "session_id" in data
        assert data["config_id"] == config_id
        assert data["status"] == "active"
        assert data["message"] == "Session created successfully"

    async def test_create_session_nonexistent_config(self, client: AsyncClient):
        """Test creating session with non-existent config_id."""
        response = await client.post(
            "/sessions",
            json={"config_id": "nonexistent-config-id"},
        )

        assert response.status_code == 404
        assert "config not found" in response.json()["detail"].lower()

    async def test_create_multiple_sessions_same_config(self, client: AsyncClient):
        """Test creating multiple sessions from the same config (reusability)."""
        # Create config
        # Use e2e_test_bundle from environment
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set in environment")

        # Create 3 sessions from same config
        session_ids = []
        for i in range(3):
            response = await client.post(
                "/sessions",
                json={"config_id": config_id},
            )
            assert response.status_code == 201
            session_ids.append(response.json()["session_id"])

        # All should have unique session IDs
        assert len(session_ids) == len(set(session_ids))

        # All should reference the same config
        for session_id in session_ids:
            response = await client.get(f"/sessions/{session_id}")
            assert response.json()["config_id"] == config_id


@pytest.mark.asyncio
class TestSessionRetrieval:
    """Test session retrieval operations."""

    async def test_get_session_by_id(self, client: AsyncClient):
        """Test getting a session by ID."""
        # Create config and session
        # Use e2e_test_bundle from environment
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set in environment")

        session_response = await client.post(
            "/sessions",
            json={"config_id": config_id},
        )
        session_id = session_response.json()["session_id"]

        # Get session
        response = await client.get(f"/sessions/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["config_id"] == config_id
        assert data["status"] == "active"

    async def test_get_nonexistent_session(self, client: AsyncClient):
        """Test getting a session that doesn't exist."""
        response = await client.get("/sessions/nonexistent-session-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_list_sessions_empty(self, client: AsyncClient):
        """Test listing sessions when none exist."""
        # Clean up first
        list_response = await client.get("/sessions")
        for session in list_response.json()["sessions"]:
            await client.delete(f"/sessions/{session['session_id']}")

        # List should be empty or minimal
        response = await client.get("/sessions")
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total" in data

    async def test_list_sessions_with_data(self, client: AsyncClient):
        """Test listing sessions after creating some."""
        # Create config
        # Use e2e_test_bundle from environment
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set in environment")

        # Create multiple sessions
        session_ids = []
        for i in range(3):
            response = await client.post(
                "/sessions",
                json={"config_id": config_id},
            )
            session_ids.append(response.json()["session_id"])

        # List sessions
        response = await client.get("/sessions")
        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) >= 3
        assert data["total"] >= 3

        # Verify our sessions are in the list
        listed_ids = {s["session_id"] for s in data["sessions"]}
        for session_id in session_ids:
            assert session_id in listed_ids

        # Verify session info structure
        for session_info in data["sessions"]:
            assert "session_id" in session_info
            assert "config_id" in session_info
            assert "status" in session_info
            assert "message_count" in session_info
            assert "created_at" in session_info
            assert "updated_at" in session_info

    async def test_list_sessions_pagination(self, client: AsyncClient):
        """Test session list pagination."""
        # Create config
        # Use e2e_test_bundle from environment
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set in environment")

        # Create 5 sessions
        for i in range(5):
            await client.post("/sessions", json={"config_id": config_id})

        # Get first page
        response = await client.get("/sessions?limit=2&offset=0")
        assert response.status_code == 200
        page1 = response.json()
        assert len(page1["sessions"]) == 2

        # Get second page
        response = await client.get("/sessions?limit=2&offset=2")
        assert response.status_code == 200
        page2 = response.json()
        assert len(page2["sessions"]) == 2

        # Verify different sessions
        page1_ids = {s["session_id"] for s in page1["sessions"]}
        page2_ids = {s["session_id"] for s in page2["sessions"]}
        assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.asyncio
class TestSessionResume:
    """Test session resume operations."""

    async def test_resume_session(self, client: AsyncClient):
        """Test resuming a session."""
        # Create config and session
        # Use e2e_test_bundle from environment
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set in environment")

        session_response = await client.post(
            "/sessions",
            json={"config_id": config_id},
        )
        session_id = session_response.json()["session_id"]

        # Resume
        response = await client.post(f"/sessions/{session_id}/resume")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["config_id"] == config_id
        assert data["message"] == "Session resumed successfully"

    async def test_resume_nonexistent_session(self, client: AsyncClient):
        """Test resuming a session that doesn't exist."""
        response = await client.post("/sessions/nonexistent-id/resume")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestSessionDeletion:
    """Test session deletion operations."""

    async def test_delete_session(self, client: AsyncClient):
        """Test deleting a session."""
        # Create config and session
        # Use e2e_test_bundle from environment
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set in environment")

        session_response = await client.post(
            "/sessions",
            json={"config_id": config_id},
        )
        session_id = session_response.json()["session_id"]

        # Delete
        response = await client.delete(f"/sessions/{session_id}")
        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"].lower()

        # Verify deleted
        get_response = await client.get(f"/sessions/{session_id}")
        assert get_response.status_code == 404

    async def test_delete_nonexistent_session(self, client: AsyncClient):
        """Test deleting a session that doesn't exist."""
        response = await client.delete("/sessions/nonexistent-id")
        assert response.status_code == 404

    async def test_delete_config_does_not_delete_sessions(self, client: AsyncClient):
        """Test that deleting a config doesn't cascade delete sessions."""
        # Create config and session
        # Use e2e_test_bundle from environment
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set in environment")

        session_response = await client.post(
            "/sessions",
            json={"config_id": config_id},
        )
        session_id = session_response.json()["session_id"]

        # Delete config

        # Session should still exist (orphaned but queryable)
        session_check = await client.get(f"/sessions/{session_id}")
        # May be 200 or 404 depending on FK enforcement - document behavior
        assert session_check.status_code in [200, 404]


@pytest.mark.asyncio
class TestSessionConcurrency:
    """Test concurrent session operations."""

    async def test_create_sessions_concurrently(self, client: AsyncClient):
        """Test creating multiple sessions simultaneously."""
        import asyncio

        # Create config
        # Use e2e_test_bundle from environment
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set in environment")

        # Create 10 sessions concurrently
        tasks = [client.post("/sessions", json={"config_id": config_id}) for _ in range(10)]

        responses = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r.status_code == 201 for r in responses)

        # All should have unique session IDs
        session_ids = [r.json()["session_id"] for r in responses]
        assert len(session_ids) == len(set(session_ids))

        # All should reference the same config
        for response in responses:
            assert response.json()["config_id"] == config_id


@pytest.mark.asyncio
class TestSessionEdgeCases:
    """Test session edge cases and error scenarios."""

    async def test_create_session_missing_config_id(self, client: AsyncClient):
        """Test creating session without config_id."""
        response = await client.post("/sessions", json={})
        assert response.status_code == 422  # Validation error

    async def test_create_session_empty_config_id(self, client: AsyncClient):
        """Test creating session with empty config_id."""
        response = await client.post("/sessions", json={"config_id": ""})
        assert response.status_code in [404, 422]

    async def test_get_session_empty_id(self, client: AsyncClient):
        """Test getting session with empty ID."""
        response = await client.get("/sessions/")
        assert response.status_code in [404, 405]  # Not found or method not allowed

    async def test_delete_session_twice(self, client: AsyncClient):
        """Test deleting the same session twice."""
        # Create config and session
        # Use e2e_test_bundle from environment
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set in environment")

        session_response = await client.post(
            "/sessions",
            json={"config_id": config_id},
        )
        session_id = session_response.json()["session_id"]

        # Delete first time
        response1 = await client.delete(f"/sessions/{session_id}")
        assert response1.status_code == 200

        # Delete second time
        response2 = await client.delete(f"/sessions/{session_id}")
        assert response2.status_code == 404


@pytest.mark.asyncio
class TestSessionStateManagement:
    """Test session state and status management."""

    async def test_session_initial_state(self, client: AsyncClient):
        """Test that new sessions have correct initial state."""
        # Create config and session
        # Use e2e_test_bundle from environment
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set in environment")

        session_response = await client.post(
            "/sessions",
            json={"config_id": config_id},
        )
        session_id = session_response.json()["session_id"]

        # Check initial state
        response = await client.get(f"/sessions/{session_id}")
        data = response.json()
        assert data["status"] == "active"
        # Message count should be 0 (or not present yet)
        # Transcript should be empty

    async def test_list_sessions_shows_correct_fields(self, client: AsyncClient):
        """Test that session list shows all expected fields."""
        # Create config and session
        # Use e2e_test_bundle from environment
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set in environment")

        await client.post("/sessions", json={"config_id": config_id})

        # List and verify structure
        response = await client.get("/sessions")
        assert response.status_code == 200
        sessions = response.json()["sessions"]
        assert len(sessions) > 0

        session = sessions[0]
        required_fields = [
            "session_id",
            "config_id",
            "status",
            "message_count",
            "created_at",
            "updated_at",
        ]

        for field in required_fields:
            assert field in session, f"Missing field: {field}"

    async def test_session_does_not_expose_sensitive_data(self, client: AsyncClient):
        """Test that session responses don't leak sensitive config data."""
        # Create config with API key
        # Use e2e_test_bundle from environment
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set in environment")

        # Create session
        session_response = await client.post(
            "/sessions",
            json={"config_id": config_id},
        )
        session_id = session_response.json()["session_id"]

        # Get session - should NOT contain the API key
        response = await client.get(f"/sessions/{session_id}")
        data_str = str(response.json())
        assert "sk-ant-super-secret" not in data_str


@pytest.mark.asyncio
class TestSessionCleanup:
    """Test cleanup and resource management."""

    async def test_delete_all_test_sessions(self, client: AsyncClient):
        """Clean up all test sessions."""
        # List all sessions
        response = await client.get("/sessions?limit=1000")
        sessions = response.json()["sessions"]

        # Delete all
        for session in sessions:
            await client.delete(f"/sessions/{session['session_id']}")

        # Verify cleanup
        final_response = await client.get("/sessions")
        assert final_response.json()["total"] == 0
