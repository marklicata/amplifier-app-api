"""Comprehensive API tests for config encryption and decrypt parameter.

Tests the decrypt query parameter functionality in the config API endpoints.
"""

import os

import pytest
from httpx import AsyncClient


# Test config with sensitive fields
TEST_CONFIG_WITH_KEYS = {
    "bundle": {"name": "test-encryption", "version": "1.0.0"},
    "includes": [{"bundle": "foundation"}],
    "session": {
        "orchestrator": {
            "module": "loop-basic",
            "source": "git+https://github.com/microsoft/amplifier-module-loop-basic@main",
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
            "config": {
                "api_key": "sk-ant-test-secret-key-12345",
                "secret": "my-secret-value",
                "token": "my-token-value",
                "model": "claude-sonnet-4-5",
            },
        }
    ],
}


@pytest.mark.asyncio
class TestConfigEncryptionAPI:
    """Test config API encryption behavior."""

    async def test_create_config_encrypts_keys(self, client: AsyncClient):
        """Test that creating a config encrypts sensitive fields in storage."""
        # Set encryption key
        os.environ["CONFIG_ENCRYPTION_KEY"] = "test-encryption-key-32-chars-min"

        response = await client.post(
            "/configs",
            json={
                "name": "test-encrypt-create",
                "config_data": TEST_CONFIG_WITH_KEYS,
            },
        )

        assert response.status_code == 201
        data = response.json()

        # Response from create should be decrypted (for usability)
        assert data["encrypted"] is False
        assert (
            data["config_data"]["providers"][0]["config"]["api_key"]
            == "sk-ant-test-secret-key-12345"
        )

        # Now retrieve with decrypt=false to verify storage
        config_id = data["config_id"]
        get_response = await client.get(f"/configs/{config_id}?decrypt=false")
        get_data = get_response.json()

        # Should be encrypted in storage
        assert get_data["encrypted"] is True
        assert get_data["config_data"]["providers"][0]["config"]["api_key"].startswith("enc:")

    async def test_get_config_decrypt_false(self, client: AsyncClient):
        """Test GET with decrypt=false returns encrypted keys."""
        # Create config first
        os.environ["CONFIG_ENCRYPTION_KEY"] = "test-encryption-key-32-chars-min"

        create_response = await client.post(
            "/configs",
            json={
                "name": "test-decrypt-false",
                "config_data": TEST_CONFIG_WITH_KEYS,
            },
        )
        config_id = create_response.json()["config_id"]

        # Get with decrypt=false (default)
        response = await client.get(f"/configs/{config_id}?decrypt=false")
        assert response.status_code == 200
        data = response.json()

        # Should be encrypted
        assert data["encrypted"] is True
        provider_config = data["config_data"]["providers"][0]["config"]
        assert provider_config["api_key"].startswith("enc:")
        assert provider_config["secret"].startswith("enc:")
        assert provider_config["token"].startswith("enc:")

        # Non-sensitive fields should not be encrypted
        assert provider_config["model"] == "claude-sonnet-4-5"

    async def test_get_config_decrypt_true(self, client: AsyncClient):
        """Test GET with decrypt=true returns plain text keys."""
        # Create config first
        os.environ["CONFIG_ENCRYPTION_KEY"] = "test-encryption-key-32-chars-min"

        create_response = await client.post(
            "/configs",
            json={
                "name": "test-decrypt-true",
                "config_data": TEST_CONFIG_WITH_KEYS,
            },
        )
        config_id = create_response.json()["config_id"]

        # Get with decrypt=true
        response = await client.get(f"/configs/{config_id}?decrypt=true")
        assert response.status_code == 200
        data = response.json()

        # Should be decrypted
        assert data["encrypted"] is False
        provider_config = data["config_data"]["providers"][0]["config"]
        assert provider_config["api_key"] == "sk-ant-test-secret-key-12345"
        assert provider_config["secret"] == "my-secret-value"
        assert provider_config["token"] == "my-token-value"
        assert provider_config["model"] == "claude-sonnet-4-5"

    async def test_get_config_default_is_encrypted(self, client: AsyncClient):
        """Test that default behavior (no decrypt param) returns encrypted keys."""
        # Create config first
        os.environ["CONFIG_ENCRYPTION_KEY"] = "test-encryption-key-32-chars-min"

        create_response = await client.post(
            "/configs",
            json={
                "name": "test-decrypt-default",
                "config_data": TEST_CONFIG_WITH_KEYS,
            },
        )
        config_id = create_response.json()["config_id"]

        # Get without decrypt parameter (should default to false/encrypted)
        response = await client.get(f"/configs/{config_id}")
        assert response.status_code == 200
        data = response.json()

        # Should be encrypted by default (secure default)
        assert data["encrypted"] is True
        assert data["config_data"]["providers"][0]["config"]["api_key"].startswith("enc:")

    async def test_encrypted_flag_consistency(self, client: AsyncClient):
        """Test that encrypted flag is consistent with actual data state."""
        os.environ["CONFIG_ENCRYPTION_KEY"] = "test-encryption-key-32-chars-min"

        create_response = await client.post(
            "/configs",
            json={
                "name": "test-flag-consistency",
                "config_data": TEST_CONFIG_WITH_KEYS,
            },
        )
        config_id = create_response.json()["config_id"]

        # Get encrypted
        encrypted_response = await client.get(f"/configs/{config_id}?decrypt=false")
        encrypted_data = encrypted_response.json()
        assert encrypted_data["encrypted"] is True
        assert encrypted_data["config_data"]["providers"][0]["config"]["api_key"].startswith("enc:")

        # Get decrypted
        decrypted_response = await client.get(f"/configs/{config_id}?decrypt=true")
        decrypted_data = decrypted_response.json()
        assert decrypted_data["encrypted"] is False
        assert not decrypted_data["config_data"]["providers"][0]["config"]["api_key"].startswith(
            "enc:"
        )

    async def test_env_var_references_not_encrypted(self, client: AsyncClient):
        """Test that ${ENV_VAR} references are not encrypted."""
        os.environ["CONFIG_ENCRYPTION_KEY"] = "test-encryption-key-32-chars-min"

        config_with_env = TEST_CONFIG_WITH_KEYS.copy()
        config_with_env["providers"][0]["config"]["api_key"] = "${ANTHROPIC_API_KEY}"

        create_response = await client.post(
            "/configs",
            json={
                "name": "test-env-vars",
                "config_data": config_with_env,
            },
        )
        config_id = create_response.json()["config_id"]

        # Get with decrypt=false
        response = await client.get(f"/configs/{config_id}?decrypt=false")
        data = response.json()

        # Env var reference should NOT be encrypted
        assert data["config_data"]["providers"][0]["config"]["api_key"] == "${ANTHROPIC_API_KEY}"


@pytest.mark.asyncio
class TestConfigEncryptionEdgeCases:
    """Test edge cases and error scenarios for encryption."""

    async def test_pre_encrypted_keys_accepted(self, client: AsyncClient):
        """Test that configs with pre-encrypted keys are accepted."""
        os.environ["CONFIG_ENCRYPTION_KEY"] = "test-encryption-key-32-chars-min"

        from amplifier_app_api.core.secrets_encryption import ConfigEncryption

        encryptor = ConfigEncryption(os.environ["CONFIG_ENCRYPTION_KEY"])

        # Pre-encrypt the API key
        plain_key = "sk-ant-pre-encrypted-123"
        encrypted_key = encryptor.fernet.encrypt(plain_key.encode()).decode()
        encrypted_key = f"enc:{encrypted_key}"

        config_with_pre_encrypted = TEST_CONFIG_WITH_KEYS.copy()
        config_with_pre_encrypted["providers"][0]["config"]["api_key"] = encrypted_key

        # Create with pre-encrypted key
        response = await client.post(
            "/configs",
            json={
                "name": "test-pre-encrypted",
                "config_data": config_with_pre_encrypted,
            },
        )

        assert response.status_code == 201
        config_id = response.json()["config_id"]

        # Retrieve with decrypt=true to verify
        get_response = await client.get(f"/configs/{config_id}?decrypt=true")
        get_data = get_response.json()

        # Should decrypt correctly
        assert get_data["config_data"]["providers"][0]["config"]["api_key"] == plain_key

    async def test_multiple_sensitive_fields_encrypted(self, client: AsyncClient):
        """Test that all sensitive field types are encrypted."""
        os.environ["CONFIG_ENCRYPTION_KEY"] = "test-encryption-key-32-chars-min"

        config_with_many_secrets = TEST_CONFIG_WITH_KEYS.copy()
        config_with_many_secrets["providers"][0]["config"] = {
            "api_key": "key123",
            "secret": "secret456",
            "password": "pass789",
            "token": "token101",
            "private_key": "pk_xyz",
            "access_key": "access123",
            "credential": "cred456",
            "model": "claude-sonnet-4-5",  # Not sensitive
        }

        create_response = await client.post(
            "/configs",
            json={
                "name": "test-many-secrets",
                "config_data": config_with_many_secrets,
            },
        )
        config_id = create_response.json()["config_id"]

        # Get encrypted version
        encrypted_response = await client.get(f"/configs/{config_id}?decrypt=false")
        encrypted_config = encrypted_response.json()["config_data"]["providers"][0]["config"]

        # All sensitive fields should be encrypted
        assert encrypted_config["api_key"].startswith("enc:")
        assert encrypted_config["secret"].startswith("enc:")
        assert encrypted_config["password"].startswith("enc:")
        assert encrypted_config["token"].startswith("enc:")
        assert encrypted_config["private_key"].startswith("enc:")
        assert encrypted_config["access_key"].startswith("enc:")
        assert encrypted_config["credential"].startswith("enc:")

        # Non-sensitive field should not be encrypted
        assert encrypted_config["model"] == "claude-sonnet-4-5"

        # Get decrypted version
        decrypted_response = await client.get(f"/configs/{config_id}?decrypt=true")
        decrypted_config = decrypted_response.json()["config_data"]["providers"][0]["config"]

        # All should decrypt correctly
        assert decrypted_config["api_key"] == "key123"
        assert decrypted_config["secret"] == "secret456"
        assert decrypted_config["password"] == "pass789"
        assert decrypted_config["token"] == "token101"
        assert decrypted_config["private_key"] == "pk_xyz"
        assert decrypted_config["access_key"] == "access123"
        assert decrypted_config["credential"] == "cred456"

    async def test_update_with_new_key_encrypts(self, client: AsyncClient):
        """Test that updating config with new keys encrypts them."""
        os.environ["CONFIG_ENCRYPTION_KEY"] = "test-encryption-key-32-chars-min"

        # Create initial config
        create_response = await client.post(
            "/configs",
            json={
                "name": "test-update-key",
                "config_data": TEST_CONFIG_WITH_KEYS,
            },
        )
        config_id = create_response.json()["config_id"]

        # Update with new API key
        updated_config = TEST_CONFIG_WITH_KEYS.copy()
        updated_config["providers"][0]["config"]["api_key"] = "sk-ant-updated-key-999"

        update_response = await client.put(
            f"/configs/{config_id}",
            json={"config_data": updated_config},
        )
        assert update_response.status_code == 200

        # Verify new key is encrypted in storage
        encrypted_response = await client.get(f"/configs/{config_id}?decrypt=false")
        encrypted_data = encrypted_response.json()
        assert encrypted_data["config_data"]["providers"][0]["config"]["api_key"].startswith(
            "enc:"
        )

        # Verify new key decrypts correctly
        decrypted_response = await client.get(f"/configs/{config_id}?decrypt=true")
        decrypted_data = decrypted_response.json()
        assert (
            decrypted_data["config_data"]["providers"][0]["config"]["api_key"]
            == "sk-ant-updated-key-999"
        )

    async def test_no_encryption_key_stores_plain(self, client: AsyncClient):
        """Test behavior when CONFIG_ENCRYPTION_KEY is not set."""
        # Remove encryption key
        os.environ.pop("CONFIG_ENCRYPTION_KEY", None)

        # Create config
        response = await client.post(
            "/configs",
            json={
                "name": "test-no-encryption",
                "config_data": TEST_CONFIG_WITH_KEYS,
            },
        )

        # Should still work but warn (keys stored in plain text)
        assert response.status_code == 201
        config_id = response.json()["config_id"]

        # Retrieve - should be plain text
        get_response = await client.get(f"/configs/{config_id}?decrypt=false")
        get_data = get_response.json()

        # Keys stored in plain text (no encryption)
        assert (
            get_data["config_data"]["providers"][0]["config"]["api_key"]
            == "sk-ant-test-secret-key-12345"
        )
        assert not get_data["config_data"]["providers"][0]["config"]["api_key"].startswith("enc:")


@pytest.mark.asyncio
class TestConfigEncryptionIntegration:
    """Integration tests for encryption with other features."""

    async def test_list_configs_does_not_include_full_config_data(self, client: AsyncClient):
        """Test that list endpoint doesn't leak encrypted config data."""
        os.environ["CONFIG_ENCRYPTION_KEY"] = "test-encryption-key-32-chars-min"

        # Create a config with secrets
        await client.post(
            "/configs",
            json={
                "name": "test-list-no-leak",
                "config_data": TEST_CONFIG_WITH_KEYS,
            },
        )

        # List configs
        response = await client.get("/configs")
        data = response.json()

        # List should only return metadata, not full config_data
        for config in data["configs"]:
            assert "config_id" in config
            assert "name" in config
            # config_data should NOT be in list response
            assert "config_data" not in config or config.get("config_data") is None

    async def test_concurrent_decrypt_requests(self, client: AsyncClient):
        """Test concurrent requests with different decrypt parameters."""
        import asyncio

        os.environ["CONFIG_ENCRYPTION_KEY"] = "test-encryption-key-32-chars-min"

        # Create config
        create_response = await client.post(
            "/configs",
            json={
                "name": "test-concurrent-decrypt",
                "config_data": TEST_CONFIG_WITH_KEYS,
            },
        )
        config_id = create_response.json()["config_id"]

        # Make 5 concurrent requests with different decrypt values
        tasks = [
            client.get(f"/configs/{config_id}?decrypt=false"),
            client.get(f"/configs/{config_id}?decrypt=true"),
            client.get(f"/configs/{config_id}?decrypt=false"),
            client.get(f"/configs/{config_id}?decrypt=true"),
            client.get(f"/configs/{config_id}"),  # default (false)
        ]

        responses = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

        # Verify response consistency
        encrypted_responses = [responses[0], responses[2], responses[4]]
        decrypted_responses = [responses[1], responses[3]]

        # All encrypted responses should have encrypted keys
        for response in encrypted_responses:
            data = response.json()
            assert data["encrypted"] is True
            assert data["config_data"]["providers"][0]["config"]["api_key"].startswith("enc:")

        # All decrypted responses should have plain keys
        for response in decrypted_responses:
            data = response.json()
            assert data["encrypted"] is False
            assert (
                data["config_data"]["providers"][0]["config"]["api_key"]
                == "sk-ant-test-secret-key-12345"
            )

    async def test_encryption_with_complex_nested_config(self, client: AsyncClient):
        """Test encryption works with deeply nested config structures."""
        os.environ["CONFIG_ENCRYPTION_KEY"] = "test-encryption-key-32-chars-min"

        complex_config = {
            "bundle": {"name": "complex", "version": "1.0.0"},
            "includes": [{"bundle": "foundation"}],
            "session": {
                "orchestrator": {
                    "module": "loop-basic",
                    "source": "test",
                    "config": {
                        "auth": {
                            "api_key": "nested-key-1",
                            "secret": "nested-secret-1",
                        }
                    },
                },
                "context": {
                    "module": "context-simple",
                    "source": "test",
                    "config": {"credentials": {"token": "nested-token-1"}},
                },
            },
            "providers": [
                {
                    "module": "provider-1",
                    "source": "test",
                    "config": {
                        "api_key": "provider-key-1",
                        "auth": {"password": "provider-pass-1"},
                    },
                },
                {
                    "module": "provider-2",
                    "source": "test",
                    "config": {"secret": "provider-secret-2"},
                },
            ],
        }

        create_response = await client.post(
            "/configs",
            json={
                "name": "test-complex-nested",
                "config_data": complex_config,
            },
        )
        config_id = create_response.json()["config_id"]

        # Get encrypted
        encrypted_response = await client.get(f"/configs/{config_id}?decrypt=false")
        encrypted_data = encrypted_response.json()["config_data"]

        # Verify all nested sensitive fields are encrypted
        assert encrypted_data["session"]["orchestrator"]["config"]["auth"]["api_key"].startswith(
            "enc:"
        )
        assert encrypted_data["session"]["orchestrator"]["config"]["auth"]["secret"].startswith(
            "enc:"
        )
        assert encrypted_data["session"]["context"]["config"]["credentials"]["token"].startswith(
            "enc:"
        )
        assert encrypted_data["providers"][0]["config"]["api_key"].startswith("enc:")
        assert encrypted_data["providers"][0]["config"]["auth"]["password"].startswith("enc:")
        assert encrypted_data["providers"][1]["config"]["secret"].startswith("enc:")


@pytest.mark.asyncio
class TestConfigEncryptionDocumentation:
    """Tests that serve as documentation examples."""

    async def test_app_workflow_encrypt_before_send(self, client: AsyncClient):
        """Example: App encrypts API key before sending to API."""
        os.environ["CONFIG_ENCRYPTION_KEY"] = "test-encryption-key-32-chars-min"

        from amplifier_app_api.core.secrets_encryption import ConfigEncryption

        # App-side: encrypt before sending
        encryptor = ConfigEncryption(os.environ["CONFIG_ENCRYPTION_KEY"])
        config_to_send = TEST_CONFIG_WITH_KEYS.copy()
        encrypted_config = encryptor.encrypt_config(config_to_send)

        # Send encrypted config to API
        response = await client.post(
            "/configs",
            json={
                "name": "test-app-workflow",
                "config_data": encrypted_config,
            },
        )

        assert response.status_code == 201
        config_id = response.json()["config_id"]

        # App-side: retrieve with decrypt=false (keeps encrypted)
        get_response = await client.get(f"/configs/{config_id}?decrypt=false")
        retrieved_config = get_response.json()["config_data"]

        # App-side: decrypt locally
        decrypted_config = encryptor.decrypt_config(retrieved_config)

        # Verify decrypted key matches original
        assert (
            decrypted_config["providers"][0]["config"]["api_key"]
            == "sk-ant-test-secret-key-12345"
        )

    async def test_admin_workflow_debug_with_decrypt(self, client: AsyncClient):
        """Example: Admin uses decrypt=true for debugging."""
        os.environ["CONFIG_ENCRYPTION_KEY"] = "test-encryption-key-32-chars-min"

        # Create config
        create_response = await client.post(
            "/configs",
            json={
                "name": "test-admin-debug",
                "config_data": TEST_CONFIG_WITH_KEYS,
            },
        )
        config_id = create_response.json()["config_id"]

        # Admin debugging: use decrypt=true to see plain text
        response = await client.get(f"/configs/{config_id}?decrypt=true")
        data = response.json()

        # Can see plain text keys for debugging
        assert data["encrypted"] is False
        assert (
            data["config_data"]["providers"][0]["config"]["api_key"]
            == "sk-ant-test-secret-key-12345"
        )
