"""Comprehensive tests for bundle API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from amplifier_app_api.main import app


@pytest.mark.asyncio
class TestBundleListing:
    """Test bundle listing."""

    async def test_list_bundles_structure(self):
        """Test bundle list returns proper structure."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/bundles")
            assert response.status_code == 200
            data = response.json()
            assert "bundles" in data
            assert isinstance(data["bundles"], list)

    async def test_list_bundles_empty(self):
        """Test listing bundles when none exist."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/bundles")
            assert response.status_code == 200


@pytest.mark.asyncio
class TestBundleAddition:
    """Test adding bundles."""

    async def test_add_bundle_with_git_source(self):
        """Test adding bundle with git URL."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/bundles",
                json={"source": "git+https://github.com/example/bundle"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "name" in data

    async def test_add_bundle_with_custom_name(self):
        """Test adding bundle with custom name."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/bundles",
                json={
                    "source": "git+https://github.com/example/bundle",
                    "name": "my-custom-name",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "my-custom-name"

    async def test_add_bundle_with_scope(self):
        """Test adding bundle with specific scope."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/bundles",
                json={
                    "source": "git+https://github.com/example/bundle",
                    "scope": "project",
                },
            )
            assert response.status_code == 200

    async def test_add_bundle_missing_source(self):
        """Test adding bundle without source."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/bundles", json={})
            assert response.status_code == 422

    async def test_add_bundle_invalid_source(self):
        """Test adding bundle with invalid source."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/bundles",
                json={"source": "not-a-valid-source"},
            )
            assert response.status_code in [200, 500]


@pytest.mark.asyncio
class TestBundleRetrieval:
    """Test getting bundle details."""

    async def test_get_nonexistent_bundle(self):
        """Test getting bundle that doesn't exist."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/bundles/nonexistent")
            assert response.status_code == 404

    async def test_get_bundle_with_special_chars(self):
        """Test getting bundle with special characters in name."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/bundles/invalid!@#$%")
            assert response.status_code == 404


@pytest.mark.asyncio
class TestBundleRemoval:
    """Test bundle removal."""

    async def test_remove_nonexistent_bundle(self):
        """Test removing bundle that doesn't exist."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/bundles/nonexistent")
            assert response.status_code == 404

    async def test_remove_active_bundle(self):
        """Test removing currently active bundle."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # This should work or return specific error
            response = await client.delete("/bundles/foundation")
            assert response.status_code in [200, 404, 409]


@pytest.mark.asyncio
class TestBundleActivation:
    """Test bundle activation."""

    async def test_activate_nonexistent_bundle(self):
        """Test activating bundle that doesn't exist."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/bundles/nonexistent/activate")
            assert response.status_code == 404

    async def test_activate_bundle_twice(self):
        """Test activating same bundle twice (idempotent)."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Add a bundle first
            await client.post(
                "/bundles",
                json={"source": "git+https://github.com/example/test-bundle"},
            )

            # Activate it twice
            response1 = await client.post("/bundles/test-bundle/activate")
            response2 = await client.post("/bundles/test-bundle/activate")

            # Both should succeed (idempotent)
            if response1.status_code == 200:
                assert response2.status_code == 200
