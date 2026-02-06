"""Tests for authentication middleware."""

from unittest.mock import patch

import jwt
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_public_paths_bypass_auth(client: AsyncClient):
    """Test that public paths don't require authentication."""
    # These should work without any auth headers
    public_paths = ["/", "/health", "/version", "/docs", "/openapi.json"]

    for path in public_paths:
        response = await client.get(path)
        # Should not get 401 Unauthorized
        assert response.status_code != 401


@pytest.mark.asyncio
async def test_auth_disabled_mode(client: AsyncClient):
    """Test authentication when AUTH_REQUIRED=false (dev mode)."""
    from amplifier_app_api.config import settings

    # Temporarily disable auth for this test
    with patch.object(settings, "auth_required", False):
        # Should work without auth headers
        response = await client.get("/sessions")
        assert response.status_code == 200  # Not 401


@pytest.mark.asyncio
async def test_missing_api_key_when_auth_enabled(client: AsyncClient):
    """Test that missing API key is rejected when auth is enabled."""
    from amplifier_app_api.config import settings

    with patch.object(settings, "auth_required", True):
        # No X-API-Key header
        response = await client.get("/sessions")
        assert response.status_code == 401
        assert "Missing X-API-Key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_missing_jwt_when_auth_enabled(client: AsyncClient):
    """Test that missing JWT is rejected when auth is enabled."""
    import uuid

    from amplifier_app_api.config import settings

    # First create an application to get a valid API key
    app_id = f"test-app-{uuid.uuid4().hex[:8]}"
    app_response = await client.post(
        "/applications",
        json={"app_id": app_id, "app_name": "Test App"},
    )
    assert app_response.status_code == 201
    api_key = app_response.json()["api_key"]

    with patch.object(settings, "auth_required", True):
        # Has API key but no JWT
        response = await client.get(
            "/sessions",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 401
        assert "Authorization header" in response.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_api_key_rejected(client: AsyncClient):
    """Test that invalid API key is rejected."""
    from amplifier_app_api.config import settings

    with patch.object(settings, "auth_required", True):
        # Create valid JWT for testing
        token = jwt.encode(
            {"sub": "test-user", "exp": 9999999999},
            settings.secret_key,
            algorithm="HS256",
        )

        response = await client.get(
            "/sessions",
            headers={
                "X-API-Key": "invalid-key-123",
                "Authorization": f"Bearer {token}",
            },
        )
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_valid_api_key_and_jwt_accepted(client: AsyncClient):
    """Test that valid API key + JWT is accepted."""
    import uuid

    from amplifier_app_api.config import settings

    # Create application
    app_id = f"valid-app-{uuid.uuid4().hex[:8]}"
    app_response = await client.post(
        "/applications",
        json={"app_id": app_id, "app_name": "Valid App"},
    )
    assert app_response.status_code == 201
    api_key = app_response.json()["api_key"]

    # Create valid JWT
    token = jwt.encode(
        {"sub": "test-user", "exp": 9999999999},
        settings.secret_key,
        algorithm="HS256",
    )

    with patch.object(settings, "auth_required", True):
        response = await client.get(
            "/sessions",
            headers={
                "X-API-Key": api_key,
                "Authorization": f"Bearer {token}",
            },
        )
        # Should get through auth (200, not 401)
        assert response.status_code != 401


@pytest.mark.asyncio
async def test_expired_jwt_rejected(client: AsyncClient):
    """Test that expired JWT is rejected."""
    import uuid

    from amplifier_app_api.config import settings

    # Create application
    app_id = f"exp-test-{uuid.uuid4().hex[:8]}"
    app_response = await client.post(
        "/applications",
        json={"app_id": app_id, "app_name": "Exp Test"},
    )
    assert app_response.status_code == 201
    api_key = app_response.json()["api_key"]

    # Create expired JWT (exp in the past)
    token = jwt.encode(
        {"sub": "test-user", "exp": 1},
        settings.secret_key,
        algorithm="HS256",
    )

    with patch.object(settings, "auth_required", True):
        response = await client.get(
            "/sessions",
            headers={
                "X-API-Key": api_key,
                "Authorization": f"Bearer {token}",
            },
        )
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_jwt_missing_sub_claim_rejected(client: AsyncClient):
    """Test that JWT without 'sub' claim is rejected."""
    import uuid

    from amplifier_app_api.config import settings

    # Create application
    app_id = f"sub-test-{uuid.uuid4().hex[:8]}"
    app_response = await client.post(
        "/applications",
        json={"app_id": app_id, "app_name": "Sub Test"},
    )
    assert app_response.status_code == 201
    api_key = app_response.json()["api_key"]

    # Create JWT without 'sub' claim
    token = jwt.encode(
        {"user": "test-user", "exp": 9999999999},  # Wrong claim name
        settings.secret_key,
        algorithm="HS256",
    )

    with patch.object(settings, "auth_required", True):
        response = await client.get(
            "/sessions",
            headers={
                "X-API-Key": api_key,
                "Authorization": f"Bearer {token}",
            },
        )
        assert response.status_code == 401
        assert "missing 'sub' claim" in response.json()["detail"]


@pytest.mark.asyncio
async def test_malformed_jwt_rejected(client: AsyncClient):
    """Test that malformed JWT is rejected."""
    import uuid

    from amplifier_app_api.config import settings

    # Create application
    app_id = f"malformed-test-{uuid.uuid4().hex[:8]}"
    app_response = await client.post(
        "/applications",
        json={"app_id": app_id, "app_name": "Malformed Test"},
    )
    assert app_response.status_code == 201
    api_key = app_response.json()["api_key"]

    with patch.object(settings, "auth_required", True):
        response = await client.get(
            "/sessions",
            headers={
                "X-API-Key": api_key,
                "Authorization": "Bearer not-a-valid-jwt",
            },
        )
        assert response.status_code == 401
        assert "Invalid JWT" in response.json()["detail"]


@pytest.mark.asyncio
async def test_jwt_only_mode_with_app_claim(client: AsyncClient):
    """Test jwt_only mode where app_id is in JWT claims."""
    from amplifier_app_api.config import settings

    # Create JWT with app_id claim
    token = jwt.encode(
        {"sub": "test-user", "app_id": "jwt-app", "exp": 9999999999},
        settings.secret_key,
        algorithm="HS256",
    )

    with patch.object(settings, "auth_required", True):
        with patch.object(settings, "auth_mode", "jwt_only"):
            response = await client.get(
                "/sessions",
                headers={"Authorization": f"Bearer {token}"},
            )
            # Should work without X-API-Key header
            assert response.status_code != 401


@pytest.mark.asyncio
async def test_jwt_only_mode_missing_app_claim_rejected(client: AsyncClient):
    """Test jwt_only mode rejects JWT without app_id claim."""
    from amplifier_app_api.config import settings

    # Create JWT without app_id claim
    token = jwt.encode(
        {"sub": "test-user", "exp": 9999999999},
        settings.secret_key,
        algorithm="HS256",
    )

    with patch.object(settings, "auth_required", True):
        with patch.object(settings, "auth_mode", "jwt_only"):
            response = await client.get(
                "/sessions",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 401
            assert "missing 'app_id' claim" in response.json()["detail"]
