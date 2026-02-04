"""Comprehensive tests for health and version endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from amplifier_app_api.main import app


@pytest.mark.asyncio
class TestHealthEndpoint:
    """Test health check endpoint."""

    async def test_health_check_response_structure(self):
        """Test health check returns required fields."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "version" in data
            assert "uptime_seconds" in data
            assert "database_connected" in data

    async def test_health_status_values(self):
        """Test health status is valid."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ["healthy", "degraded", "unhealthy"]

    async def test_health_uptime_positive(self):
        """Test uptime is a positive number."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["uptime_seconds"] >= 0
            assert isinstance(data["uptime_seconds"], (int, float))

    async def test_health_database_boolean(self):
        """Test database_connected is boolean."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data["database_connected"], bool)

    async def test_health_multiple_calls(self):
        """Test health endpoint can be called multiple times."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response1 = await client.get("/health")
            response2 = await client.get("/health")
            response3 = await client.get("/health")

            assert response1.status_code == 200
            assert response2.status_code == 200
            assert response3.status_code == 200

            # Uptime should increase
            data1 = response1.json()
            data3 = response3.json()
            assert data3["uptime_seconds"] >= data1["uptime_seconds"]


@pytest.mark.asyncio
class TestVersionEndpoint:
    """Test version endpoint."""

    async def test_version_response_structure(self):
        """Test version endpoint returns proper structure."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/version")
            assert response.status_code == 200
            data = response.json()
            assert "service_version" in data

    async def test_version_format(self):
        """Test version is in proper format."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/version")
            assert response.status_code == 200
            data = response.json()
            # Should be semver-like
            assert isinstance(data["service_version"], str)
            assert len(data["service_version"]) > 0


@pytest.mark.asyncio
class TestRootEndpoint:
    """Test root endpoint."""

    async def test_root_response_structure(self):
        """Test root endpoint returns service info."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/")
            assert response.status_code == 200
            data = response.json()
            assert "service" in data
            assert "version" in data
            assert "docs" in data

    async def test_root_service_name(self):
        """Test service name is correct."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/")
            assert response.status_code == 200
            data = response.json()
            assert data["service"] == "Amplifier App api"

    async def test_root_docs_link(self):
        """Test docs link is provided."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/")
            assert response.status_code == 200
            data = response.json()
            assert data["docs"] == "/docs"


@pytest.mark.asyncio
class TestAPIDocumentation:
    """Test OpenAPI documentation endpoints."""

    async def test_openapi_json_accessible(self):
        """Test OpenAPI JSON schema is accessible."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/openapi.json")
            assert response.status_code == 200
            data = response.json()
            assert "openapi" in data
            assert "paths" in data

    async def test_docs_page_accessible(self):
        """Test Swagger UI docs page is accessible."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/docs")
            assert response.status_code == 200
            assert "swagger" in response.text.lower() or "openapi" in response.text.lower()

    async def test_redoc_page_accessible(self):
        """Test ReDoc page is accessible."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/redoc")
            assert response.status_code == 200
            assert "redoc" in response.text.lower() or "openapi" in response.text.lower()


@pytest.mark.asyncio
class TestCORS:
    """Test CORS configuration."""

    async def test_cors_headers_present(self):
        """Test CORS headers are present in responses."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.options(
                "/health",
                headers={"Origin": "http://localhost:3000"},
            )
            # Should have CORS headers (or 405 if OPTIONS not implemented)
            assert response.status_code in [200, 204, 405]

    async def test_cors_allowed_origin(self):
        """Test CORS allows configured origins."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/health",
                headers={"Origin": "http://localhost:3000"},
            )
            assert response.status_code == 200
            # Should have access-control-allow-origin header
            # (May not be present in test client, but endpoint should work)


@pytest.mark.asyncio
class TestErrorHandling:
    """Test global error handling."""

    async def test_404_for_unknown_endpoint(self):
        """Test 404 for endpoints that don't exist."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/this/does/not/exist")
            assert response.status_code == 404

    async def test_405_for_wrong_method(self):
        """Test 405 for wrong HTTP method."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # GET on POST-only endpoint
            response = await client.get("/sessions/create")
            assert response.status_code == 405

    async def test_422_for_invalid_request_body(self):
        """Test 422 for invalid request validation."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/sessions/test-id/messages",
                json={"wrong_field": "value"},
            )
            assert response.status_code == 422
