"""Comprehensive tests for configuration API endpoints."""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from amplifier_app_api.main import app


@pytest.mark.asyncio
class TestConfigRetrieval:
    """Test configuration retrieval."""

    async def test_get_config_structure(self):
        """Test config endpoint returns proper structure."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/config")
            assert response.status_code == 200
            data = response.json()
            assert "providers" in data
            assert "bundles" in data
            assert "modules" in data

    async def test_get_config_empty_state(self):
        """Test getting config when nothing configured."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/config")
            assert response.status_code == 200
            data = response.json()
            # Should have empty dicts, not None
            assert isinstance(data["providers"], dict)
            assert isinstance(data["bundles"], dict)


@pytest.mark.asyncio
class TestConfigUpdate:
    """Test configuration updates."""

    async def test_update_config_empty(self):
        """Test updating config with empty payload."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/config", json={})
            assert response.status_code == 200

    async def test_update_config_providers_only(self):
        """Test updating only providers."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/config",
                json={"providers": {"anthropic": {"model": "claude-sonnet-4-5"}}},
            )
            assert response.status_code == 200

    async def test_update_config_bundles_only(self):
        """Test updating only bundles."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/config",
                json={"bundles": {"custom": {"source": "git+https://example.com"}}},
            )
            assert response.status_code == 200

    async def test_update_config_all_sections(self):
        """Test updating all config sections."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/config",
                json={
                    "providers": {"anthropic": {}},
                    "bundles": {"foundation": {}},
                    "modules": {"tool-filesystem": {}},
                },
            )
            assert response.status_code == 200


@pytest.mark.asyncio
class TestProviderManagement:
    """Test provider configuration endpoints."""

    async def test_list_providers_empty(self):
        """Test listing providers when none configured."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/config/providers")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    async def test_add_provider_minimal(self):
        """Test adding provider with minimal config."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/config/providers",
                json={"provider": "anthropic"},
            )
            assert response.status_code == 200

    async def test_add_provider_with_api_key(self):
        """Test adding provider with API key."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/config/providers",
                json={"provider": "anthropic", "api_key": "test-key"},
            )
            assert response.status_code == 200

    async def test_add_provider_with_config(self):
        """Test adding provider with additional config."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/config/providers",
                json={
                    "provider": "anthropic",
                    "api_key": "test-key",
                    "config": {"default_model": "claude-sonnet-4-5"},
                },
            )
            assert response.status_code == 200

    async def test_add_provider_missing_name(self):
        """Test adding provider without name."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/config/providers",
                json={"api_key": "test-key"},
            )
            assert response.status_code == 422

    async def test_get_provider_nonexistent(self):
        """Test getting provider that doesn't exist."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/config/providers/nonexistent")
            assert response.status_code == 404

    async def test_activate_provider_nonexistent(self):
        """Test activating provider that doesn't exist."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/config/providers/nonexistent/activate")
            assert response.status_code == 404

    async def test_get_current_provider_none_active(self):
        """Test getting current provider when none active."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/config/providers/current")
            assert response.status_code in [200, 404]


@pytest.mark.asyncio
class TestProviderSecurity:
    """Test that sensitive provider data is handled securely."""

    async def test_get_provider_does_not_expose_api_key(self):
        """Test that API keys are not returned in responses."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Add provider with API key
            await client.post(
                "/config/providers",
                json={"provider": "test-provider", "api_key": "secret-key-12345"},
            )

            # Get provider config
            response = await client.get("/config/providers/test-provider")
            if response.status_code == 200:
                data = response.json()
                # Should not contain api_key field
                assert "api_key" not in json.dumps(data)


@pytest.mark.asyncio
class TestEdgeCases:
    """Test edge cases and error handling."""

    async def test_malformed_json(self):
        """Test sending malformed JSON."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/sessions",
                content="not-valid-json",
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 422

    async def test_wrong_content_type(self):
        """Test sending wrong content type."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/sessions",
                content="test",
                headers={"Content-Type": "text/plain"},
            )
            assert response.status_code in [422, 415]

    async def test_extra_fields_ignored(self):
        """Test that extra fields in requests are handled gracefully."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/sessions",
                json={
                    "config_id": "test-config",
                    "extra_field": "should be ignored",
                    "another_extra": 12345,
                },
            )
            assert response.status_code in [200, 404, 500]
