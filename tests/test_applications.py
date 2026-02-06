"""Tests for application management API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_application(client: AsyncClient):
    """Test creating a new application."""
    # Use unique app_id to avoid conflicts with other tests
    import uuid

    unique_id = f"test-mobile-app-{uuid.uuid4().hex[:8]}"

    response = await client.post(
        "/applications",
        json={
            "app_id": unique_id,
            "app_name": "Test Mobile App",
            "settings": {"feature_flags": {"advanced_mode": True}},
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["app_id"] == unique_id
    assert data["app_name"] == "Test Mobile App"
    assert "api_key" in data
    assert data["api_key"].startswith("app_")
    assert data["is_active"] is True
    assert "created_at" in data
    assert data["message"] == "Application registered successfully"


@pytest.mark.asyncio
async def test_create_application_duplicate_id(client: AsyncClient):
    """Test creating application with duplicate app_id fails."""
    # Create first application
    await client.post(
        "/applications",
        json={"app_id": "duplicate-app", "app_name": "First App"},
    )

    # Attempt to create with same app_id
    response = await client.post(
        "/applications",
        json={"app_id": "duplicate-app", "app_name": "Second App"},
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_application_invalid_app_id_format(client: AsyncClient):
    """Test creating application with invalid app_id format fails."""
    response = await client.post(
        "/applications",
        json={"app_id": "Invalid App ID!", "app_name": "Test App"},
    )

    # Should fail validation (app_id must be lowercase with hyphens only)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_applications_empty(client: AsyncClient):
    """Test listing applications returns a list (may have data from other tests)."""
    response = await client.get("/applications")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # May not be empty if other tests have run


@pytest.mark.asyncio
async def test_list_applications(client: AsyncClient):
    """Test listing applications."""
    import uuid

    # Create test applications with unique IDs
    app1_id = f"app-1-{uuid.uuid4().hex[:8]}"
    app2_id = f"app-2-{uuid.uuid4().hex[:8]}"

    await client.post(
        "/applications",
        json={"app_id": app1_id, "app_name": "First App"},
    )
    await client.post(
        "/applications",
        json={"app_id": app2_id, "app_name": "Second App"},
    )

    response = await client.get("/applications")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2  # At least our 2 apps

    # Find our apps in the list
    app_ids = [app["app_id"] for app in data]
    assert app1_id in app_ids
    assert app2_id in app_ids

    # Check that API keys are NOT included in list
    for app in data:
        assert "api_key" not in app
        assert "app_id" in app
        assert "app_name" in app
        assert "is_active" in app
        assert "created_at" in app
        assert "updated_at" in app

    # Verify our apps are ordered correctly (most recent first)
    app1_idx = app_ids.index(app1_id)
    app2_idx = app_ids.index(app2_id)
    assert app2_idx < app1_idx  # app-2 created second, should be first in list


@pytest.mark.asyncio
async def test_get_application(client: AsyncClient):
    """Test getting specific application details."""
    # Create application
    await client.post(
        "/applications",
        json={"app_id": "test-app", "app_name": "Test App"},
    )

    # Get application details
    response = await client.get("/applications/test-app")

    assert response.status_code == 200
    data = response.json()
    assert data["app_id"] == "test-app"
    assert data["app_name"] == "Test App"
    assert "api_key" not in data  # API key should not be returned
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_get_application_not_found(client: AsyncClient):
    """Test getting non-existent application."""
    response = await client.get("/applications/nonexistent-app")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_application(client: AsyncClient):
    """Test deleting an application."""
    # Create application
    await client.post(
        "/applications",
        json={"app_id": "delete-me", "app_name": "Delete Me"},
    )

    # Delete application
    response = await client.delete("/applications/delete-me")

    assert response.status_code == 200
    assert "deleted successfully" in response.json()["message"]

    # Verify it's gone
    get_response = await client.get("/applications/delete-me")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_application_not_found(client: AsyncClient):
    """Test deleting non-existent application."""
    response = await client.delete("/applications/nonexistent")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_regenerate_api_key(client: AsyncClient):
    """Test regenerating API key for an application."""
    import uuid

    # Create application with unique ID
    app_id = f"regen-app-{uuid.uuid4().hex[:8]}"
    create_response = await client.post(
        "/applications",
        json={"app_id": app_id, "app_name": "Regen App"},
    )
    assert create_response.status_code == 201
    original_api_key = create_response.json()["api_key"]

    # Regenerate API key
    response = await client.post(f"/applications/{app_id}/regenerate-key")

    assert response.status_code == 200
    data = response.json()
    assert data["app_id"] == app_id
    assert "api_key" in data
    assert data["api_key"] != original_api_key  # New key is different
    assert data["api_key"].startswith("app_")
    assert "regenerated successfully" in data["message"]


@pytest.mark.asyncio
async def test_regenerate_api_key_not_found(client: AsyncClient):
    """Test regenerating API key for non-existent application."""
    response = await client.post("/applications/nonexistent/regenerate-key")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_api_key_format(client: AsyncClient):
    """Test that generated API keys have correct format."""
    import uuid

    app_id = f"format-test-{uuid.uuid4().hex[:8]}"
    response = await client.post(
        "/applications",
        json={"app_id": app_id, "app_name": "Format Test"},
    )

    assert response.status_code == 201
    api_key = response.json()["api_key"]

    # Check format: app_{base64url_chars}
    assert api_key.startswith("app_")
    assert len(api_key) > 40  # Should be reasonably long
    # URL-safe characters only after prefix
    key_part = api_key[4:]
    allowed_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
    assert all(c in allowed_chars for c in key_part)
