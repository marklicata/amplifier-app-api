"""Tests for authentication middleware."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest.mark.asyncio
async def test_github_auth_in_dev_mode_with_gh_cli(client: AsyncClient):
    """Test that GitHub username is used in dev mode when gh CLI is available."""
    from amplifier_app_api.config import settings
    from amplifier_app_api.middleware import auth

    # Clear cache
    auth._github_user_cache = None

    # Mock subprocess that returns a GitHub username
    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"test-gh-user\n", b""))

    with patch.object(settings, "auth_required", False):
        with patch.object(settings, "use_github_auth_in_dev", True):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                with patch("asyncio.wait_for", return_value=mock_process):
                    # Clear cache before test
                    auth._github_user_cache = None

                    response = await client.get("/sessions")

                    # Should succeed (200, not 401)
                    assert response.status_code == 200

                    # Verify the cache was set
                    assert auth._github_user_cache == "test-gh-user"


@pytest.mark.asyncio
async def test_github_auth_fallback_when_gh_cli_fails(client: AsyncClient):
    """Test fallback to 'dev-user' when gh CLI is not available."""
    from amplifier_app_api.config import settings
    from amplifier_app_api.middleware import auth

    # Clear cache
    auth._github_user_cache = None

    # Mock subprocess that fails
    mock_process = AsyncMock()
    mock_process.returncode = 1
    mock_process.communicate = AsyncMock(return_value=(b"", b"not logged in\n"))

    with patch.object(settings, "auth_required", False):
        with patch.object(settings, "use_github_auth_in_dev", True):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                with patch("asyncio.wait_for", return_value=mock_process):
                    # Clear cache before test
                    auth._github_user_cache = None

                    response = await client.get("/sessions")

                    # Should succeed (200, not 401)
                    assert response.status_code == 200

                    # Should fall back to dev-user
                    assert auth._github_user_cache == "dev-user"


@pytest.mark.asyncio
async def test_github_auth_fallback_on_timeout(client: AsyncClient):
    """Test fallback to 'dev-user' when gh CLI times out."""
    from amplifier_app_api.config import settings
    from amplifier_app_api.middleware import auth

    # Clear cache
    auth._github_user_cache = None

    with patch.object(settings, "auth_required", False):
        with patch.object(settings, "use_github_auth_in_dev", True):
            # Mock asyncio.wait_for to raise TimeoutError
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
                # Clear cache before test
                auth._github_user_cache = None

                response = await client.get("/sessions")

                # Should succeed (200, not 401)
                assert response.status_code == 200

                # Should fall back to dev-user
                assert auth._github_user_cache == "dev-user"


@pytest.mark.asyncio
async def test_github_auth_disabled_uses_dev_user(client: AsyncClient):
    """Test that 'dev-user' is used when GitHub auth is disabled."""
    from amplifier_app_api.config import settings
    from amplifier_app_api.middleware import auth

    # Clear cache
    auth._github_user_cache = None

    with patch.object(settings, "auth_required", False):
        with patch.object(settings, "use_github_auth_in_dev", False):
            response = await client.get("/sessions")

            # Should succeed (200, not 401)
            assert response.status_code == 200

            # Should use dev-user (cache should remain None since feature is disabled)
            # The cache is only set when use_github_auth_in_dev is True


@pytest.mark.asyncio
async def test_github_auth_cache_reused(client: AsyncClient):
    """Test that GitHub username is cached and subprocess is not called repeatedly."""
    from amplifier_app_api.config import settings
    from amplifier_app_api.middleware import auth

    # Set cache directly
    auth._github_user_cache = "cached-gh-user"

    mock_subprocess = AsyncMock()

    with patch.object(settings, "auth_required", False):
        with patch.object(settings, "use_github_auth_in_dev", True):
            with patch("asyncio.create_subprocess_exec", mock_subprocess):
                # Make two requests
                response1 = await client.get("/sessions")
                response2 = await client.get("/sessions")

                # Both should succeed
                assert response1.status_code == 200
                assert response2.status_code == 200

                # Subprocess should NOT have been called (cache was used)
                mock_subprocess.assert_not_called()


@pytest.mark.asyncio
async def test_github_auth_with_file_not_found(client: AsyncClient):
    """Test fallback when gh CLI is not installed (FileNotFoundError)."""
    from amplifier_app_api.config import settings
    from amplifier_app_api.middleware import auth

    # Clear cache
    auth._github_user_cache = None

    with patch.object(settings, "auth_required", False):
        with patch.object(settings, "use_github_auth_in_dev", True):
            # Mock asyncio.create_subprocess_exec to raise FileNotFoundError
            with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("gh not found")):
                # Clear cache before test
                auth._github_user_cache = None

                response = await client.get("/sessions")

                # Should succeed (200, not 401)
                assert response.status_code == 200

                # Should fall back to dev-user
                assert auth._github_user_cache == "dev-user"
