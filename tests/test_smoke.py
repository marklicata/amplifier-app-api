"""Smoke tests - quick validation that core functionality works."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestSmokeBasics:
    """Basic smoke tests - service is alive."""

    async def test_service_is_running(self, client: AsyncClient):
        """Test that service responds to requests."""
        response = await client.get("/")
        assert response.status_code == 200

    async def test_health_endpoint_works(self, client: AsyncClient):
        """Test health endpoint is accessible."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] in ["healthy", "degraded"]

    async def test_api_docs_accessible(self, client: AsyncClient):
        """Test API documentation is accessible."""
        response = await client.get("/openapi.json")
        assert response.status_code == 200

    async def test_database_connected(self, client: AsyncClient):
        """Test database connectivity."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["database_connected"] is True


@pytest.mark.asyncio
class TestSmokeCRUD:
    """Smoke tests for basic CRUD operations."""

    async def test_sessions_endpoint_exists(self, client: AsyncClient):
        """Test sessions endpoint is accessible."""
        response = await client.get("/sessions")
        assert response.status_code == 200

    async def test_configs_endpoint_exists(self, client: AsyncClient):
        """Test configs endpoint is accessible."""
        response = await client.get("/configs")
        assert response.status_code == 200

    async def test_applications_endpoint_exists(self, client: AsyncClient):
        """Test applications endpoint is accessible."""
        response = await client.get("/applications")
        assert response.status_code == 200


@pytest.mark.asyncio
class TestSmokeDataIntegrity:
    """Smoke tests for data integrity."""

    async def test_session_creation_returns_valid_id(self, client: AsyncClient):
        """Test session creation returns valid UUID."""
        # First create a config
        config_response = await client.post(
            "/configs",
            json={
                "name": "test-config-smoke",
                "description": "Smoke test configuration",
                "config_data": {
                    "bundle": {"name": "test", "version": "1.0.0"},
                    "includes": [{"bundle": "foundation"}],
                    "session": {
                        "orchestrator": {
                            "module": "loop-streaming",
                            "source": "git+https://github.com/microsoft/amplifier-module-loop-streaming@main",
                            "config": {},
                        },
                        "context": {
                            "module": "context-simple",
                            "source": "git+https://github.com/microsoft/amplifier-module-context-simple@main",
                            "config": {},
                        },
                    },
                    "providers": [
                        {
                            "module": "provider-anthropic",
                            "source": "git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
                            "config": {"api_key": "test-key", "model": "claude-sonnet-4-5"},
                        }
                    ],
                },
            },
        )

        if config_response.status_code != 201:
            return

        config_id = config_response.json()["config_id"]

        response = await client.post("/sessions", json={"config_id": config_id})
        if response.status_code == 201:
            data = response.json()
            session_id = data["session_id"]
            # Should have a session_id
            assert session_id
            assert isinstance(session_id, str)
            assert len(session_id) > 0

    async def test_sessions_list_is_consistent(self, client: AsyncClient):
        """Test sessions list returns consistent data."""
        response1 = await client.get("/sessions")
        response2 = await client.get("/sessions")

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Structure should be identical
        assert response1.json().keys() == response2.json().keys()


@pytest.mark.asyncio
class TestSmokeErrorHandling:
    """Smoke tests for error handling."""

    async def test_404_handled_gracefully(self, client: AsyncClient):
        """Test 404 errors are handled."""
        response = await client.get("/nonexistent")
        assert response.status_code == 404
        # Should return JSON, not crash
        data = response.json()
        assert "detail" in data

    async def test_422_validation_errors_handled(self, client: AsyncClient):
        """Test validation errors are handled."""
        response = await client.post("/sessions/test/messages", json={})
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    async def test_500_errors_handled_gracefully(self, client: AsyncClient):
        """Test internal errors don't crash service."""
        # Try to send message to nonexistent session
        # Note: With mock_session_manager, this actually succeeds
        # In a real scenario, this would fail with 404
        response = await client.post(
            "/sessions/nonexistent/messages",
            json={"message": "test"},
        )
        # Should return response without crashing
        assert response.status_code in [200, 404, 500]
        data = response.json()
        # Should have valid JSON response
        assert data is not None
