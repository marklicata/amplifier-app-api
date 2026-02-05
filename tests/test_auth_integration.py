"""Integration tests for authentication flows."""

import jwt
import pytest
from httpx import AsyncClient
from unittest.mock import patch


@pytest.mark.asyncio
async def test_full_auth_flow_api_key_plus_jwt(client: AsyncClient):
    """Test complete authentication flow: register app, create JWT, make authenticated request."""
    from amplifier_app_api.config import settings

    # Step 1: Register application
    app_response = await client.post(
        "/applications",
        json={
            "app_id": "integration-test-app",
            "app_name": "Integration Test App",
        },
    )
    assert app_response.status_code == 201
    api_key = app_response.json()["api_key"]
    assert api_key.startswith("app_")

    # Step 2: Create JWT for user
    user_id = "user-123"
    token = jwt.encode(
        {"sub": user_id, "exp": 9999999999},
        settings.secret_key,
        algorithm="HS256",
    )

    # Step 3: Make authenticated request to create session
    with patch.object(settings, "auth_required", True):
        # First create a config
        config_response = await client.post(
            "/configs",
            json={
                "name": "auth-test-config",
                "yaml_content": """
bundle:
  name: auth-test
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
            headers={
                "X-API-Key": api_key,
                "Authorization": f"Bearer {token}",
            },
        )

        # Auth should succeed
        assert config_response.status_code != 401


@pytest.mark.asyncio
async def test_api_key_rotation_workflow(client: AsyncClient):
    """Test API key rotation: regenerate key and verify old key stops working."""
    from amplifier_app_api.config import settings

    # Register application
    app_response = await client.post(
        "/applications",
        json={"app_id": "rotation-app", "app_name": "Rotation App"},
    )
    old_api_key = app_response.json()["api_key"]

    # Create JWT
    token = jwt.encode(
        {"sub": "rotation-user", "exp": 9999999999},
        settings.secret_key,
        algorithm="HS256",
    )

    with patch.object(settings, "auth_required", True):
        # Verify old key works
        response1 = await client.get(
            "/sessions",
            headers={
                "X-API-Key": old_api_key,
                "Authorization": f"Bearer {token}",
            },
        )
        assert response1.status_code != 401

        # Regenerate API key
        regen_response = await client.post("/applications/rotation-app/regenerate-key")
        assert regen_response.status_code == 200
        new_api_key = regen_response.json()["api_key"]
        assert new_api_key != old_api_key

        # Old key should no longer work
        response2 = await client.get(
            "/sessions",
            headers={
                "X-API-Key": old_api_key,
                "Authorization": f"Bearer {token}",
            },
        )
        assert response2.status_code == 401

        # New key should work
        response3 = await client.get(
            "/sessions",
            headers={
                "X-API-Key": new_api_key,
                "Authorization": f"Bearer {token}",
            },
        )
        assert response3.status_code != 401


@pytest.mark.asyncio
async def test_jwt_only_mode_integration(client: AsyncClient):
    """Test jwt_only authentication mode end-to-end."""
    from amplifier_app_api.config import settings

    # Create JWT with app_id claim
    token = jwt.encode(
        {
            "sub": "jwt-only-user",
            "app_id": "jwt-embedded-app",
            "exp": 9999999999,
        },
        settings.secret_key,
        algorithm="HS256",
    )

    with patch.object(settings, "auth_required", True):
        with patch.object(settings, "auth_mode", "jwt_only"):
            # Create config without X-API-Key header
            config_response = await client.post(
                "/configs",
                json={
                    "name": "jwt-only-config",
                    "yaml_content": """
bundle:
  name: jwt-only-test
includes:
  - bundle: foundation
session:
  orchestrator: loop-basic
  context: context-simple
providers:
  - module: provider-anthropic
    config:
      api_key: test
      model: claude-sonnet-4-5
""",
                },
                headers={"Authorization": f"Bearer {token}"},
            )

            # Should work without X-API-Key
            assert config_response.status_code != 401
