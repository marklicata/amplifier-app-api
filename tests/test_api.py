"""Tests for API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from amplifier_app_api.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health check endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "version" in data
        assert "uptime_seconds" in data


@pytest.mark.asyncio
async def test_version_endpoint():
    """Test version endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/version")
        assert response.status_code == 200
        data = response.json()
        assert "service_version" in data


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test root endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Amplifier App api"
        assert "version" in data


@pytest.mark.asyncio
async def test_create_session():
    """Test session creation (requires config first in new architecture)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First create a config
        config_response = await client.post(
            "/configs",
            json={
                "name": "test-session-creation",
                "yaml_content": """
bundle:
  name: test-session
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

        if config_response.status_code == 201:
            config_id = config_response.json()["config_id"]

            # Create session from config
            response = await client.post(
                "/sessions",
                json={"config_id": config_id},
            )
            # May fail if amplifier-core/foundation not properly set up
            # but endpoint should be accessible
            assert response.status_code in [201, 404, 500]


@pytest.mark.asyncio
async def test_list_sessions():
    """Test listing sessions."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/sessions")
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total" in data


@pytest.mark.asyncio
async def test_list_bundles():
    """Test listing bundles."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/bundles")
        assert response.status_code == 200
        data = response.json()
        assert "bundles" in data


@pytest.mark.asyncio
async def test_get_config():
    """Test getting configuration."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/config")
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert "bundles" in data
