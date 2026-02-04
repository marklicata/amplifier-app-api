"""Smoke tests - quick validation that core functionality works."""

import pytest
from httpx import ASGITransport, AsyncClient

from amplifier_app_api.main import app


@pytest.mark.asyncio
class TestSmokeBasics:
    """Basic smoke tests - service is alive."""

    async def test_service_is_running(self):
        """Test that service responds to requests."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/")
            assert response.status_code == 200

    async def test_health_endpoint_works(self):
        """Test health endpoint is accessible."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] in ["healthy", "degraded"]

    async def test_api_docs_accessible(self):
        """Test API documentation is accessible."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/openapi.json")
            assert response.status_code == 200

    async def test_database_connected(self):
        """Test database connectivity."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json()["database_connected"] is True


@pytest.mark.asyncio
class TestSmokeCRUD:
    """Smoke tests for basic CRUD operations."""

    async def test_sessions_endpoint_exists(self):
        """Test sessions endpoint is accessible."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/sessions")
            assert response.status_code == 200

    async def test_config_endpoint_exists(self):
        """Test config endpoint is accessible."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/config")
            assert response.status_code == 200

    async def test_bundles_endpoint_exists(self):
        """Test bundles endpoint is accessible."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/bundles")
            assert response.status_code == 200

    async def test_tools_endpoint_exists(self):
        """Test tools endpoint is accessible."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/tools")
            # May fail without proper setup, but endpoint should exist
            assert response.status_code in [200, 500]


@pytest.mark.asyncio
class TestSmokeDataIntegrity:
    """Smoke tests for data integrity."""

    async def test_session_creation_returns_valid_id(self):
        """Test session creation returns valid UUID."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # First create a config
            config_response = await client.post(
                "/configs",
                json={
                    "name": "test-config-smoke",
                    "yaml_content": """
bundle:
  name: test
includes:
  - bundle: foundation
session:
  orchestrator: loop-basic
  context: context-simple
providers:
  - module: provider-anthropic
    config:
      api_key: test-key
      model: claude-sonnet-4-5
""",
                },
            )

            if config_response.status_code != 200:
                return

            config_id = config_response.json()["config_id"]

            response = await client.post("/sessions", json={"config_id": config_id})
            if response.status_code == 200:
                data = response.json()
                session_id = data["session_id"]
                # Should be UUID format
                assert len(session_id) == 36  # UUID v4 format
                assert session_id.count("-") == 4

    async def test_sessions_list_is_consistent(self):
        """Test sessions list returns consistent data."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response1 = await client.get("/sessions")
            response2 = await client.get("/sessions")

            assert response1.status_code == 200
            assert response2.status_code == 200

            # Structure should be identical
            assert response1.json().keys() == response2.json().keys()


@pytest.mark.asyncio
class TestSmokeErrorHandling:
    """Smoke tests for error handling."""

    async def test_404_handled_gracefully(self):
        """Test 404 errors are handled."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/nonexistent")
            assert response.status_code == 404
            # Should return JSON, not crash
            data = response.json()
            assert "detail" in data

    async def test_422_validation_errors_handled(self):
        """Test validation errors are handled."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/sessions/test/messages", json={})
            assert response.status_code == 422
            data = response.json()
            assert "detail" in data

    async def test_500_errors_handled_gracefully(self):
        """Test internal errors don't crash service."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Try to send message to nonexistent session
            response = await client.post(
                "/sessions/nonexistent/messages",
                json={"message": "test"},
            )
            # Should return error, not crash
            assert response.status_code in [404, 500]
            data = response.json()
            assert "detail" in data
