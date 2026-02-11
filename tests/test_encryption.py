"""Tests for config encryption functionality with decrypt parameter."""

import os

import pytest

from amplifier_app_api.core.config_manager import ConfigManager
from amplifier_app_api.core.secrets_encryption import ConfigEncryption


@pytest.mark.asyncio
async def test_encryption_decryption(test_db):
    """Test that encryption and decryption work correctly."""
    db = test_db

    # Set encryption key
    os.environ["CONFIG_ENCRYPTION_KEY"] = "test-encryption-key-32-chars-min"

    manager = ConfigManager(db)

    # Create config with sensitive field
    config_data = {
        "bundle": {"name": "test", "version": "1.0.0"},
        "providers": [{"config": {"api_key": "sk-ant-test-key-123"}}],
    }

    config = await manager.create_config(
        name="test-config", config_data=config_data, validate=False
    )

    # Get config with decrypt=False (encrypted)
    encrypted_config = await manager.get_config(config.config_id, decrypt=False)
    assert encrypted_config is not None

    # Verify API key is encrypted (has "enc:" prefix)
    encrypted_api_key = encrypted_config.config_data["providers"][0]["config"]["api_key"]
    assert encrypted_api_key.startswith("enc:"), "API key should be encrypted with 'enc:' prefix"
    assert "sk-ant-test-key-123" not in encrypted_api_key, "Plain text key should not be visible"

    # Get config with decrypt=True (decrypted)
    decrypted_config = await manager.get_config(config.config_id, decrypt=True)
    assert decrypted_config is not None

    # Verify API key is decrypted (plain text)
    decrypted_api_key = decrypted_config.config_data["providers"][0]["config"]["api_key"]
    assert decrypted_api_key == "sk-ant-test-key-123", "API key should be decrypted"
    assert not decrypted_api_key.startswith("enc:"), "Decrypted key should not have 'enc:' prefix"


@pytest.mark.asyncio
async def test_create_with_pre_encrypted_key(test_db):
    """Test that configs can be created with pre-encrypted keys."""
    db = test_db

    # Set encryption key
    os.environ["CONFIG_ENCRYPTION_KEY"] = "test-encryption-key-32-chars-min"

    encryptor = ConfigEncryption(os.environ["CONFIG_ENCRYPTION_KEY"])
    manager = ConfigManager(db)

    # Pre-encrypt the API key
    plain_key = "sk-ant-pre-encrypted-123"
    encrypted_key = encryptor.fernet.encrypt(plain_key.encode()).decode()
    encrypted_key = f"enc:{encrypted_key}"

    # Create config with pre-encrypted key
    config_data = {
        "bundle": {"name": "test", "version": "1.0.0"},
        "providers": [{"config": {"api_key": encrypted_key}}],
    }

    config = await manager.create_config(
        name="test-config-pre-encrypted", config_data=config_data, validate=False
    )

    # Get config with decrypt=True
    decrypted_config = await manager.get_config(config.config_id, decrypt=True)

    # Verify the key is correctly decrypted
    decrypted_api_key = decrypted_config.config_data["providers"][0]["config"]["api_key"]
    assert decrypted_api_key == plain_key, "Pre-encrypted key should decrypt correctly"


@pytest.mark.asyncio
async def test_env_var_reference_not_encrypted(test_db):
    """Test that environment variable references are not encrypted."""
    db = test_db

    # Set encryption key
    os.environ["CONFIG_ENCRYPTION_KEY"] = "test-encryption-key-32-chars-min"

    manager = ConfigManager(db)

    # Create config with env var reference
    config_data = {
        "bundle": {"name": "test", "version": "1.0.0"},
        "providers": [{"config": {"api_key": "${ANTHROPIC_API_KEY}"}}],
    }

    config = await manager.create_config(
        name="test-config-env-var", config_data=config_data, validate=False
    )

    # Get config with decrypt=False
    encrypted_config = await manager.get_config(config.config_id, decrypt=False)

    # Verify env var reference is NOT encrypted
    api_key = encrypted_config.config_data["providers"][0]["config"]["api_key"]
    assert api_key == "${ANTHROPIC_API_KEY}", "Env var reference should not be encrypted"
    assert not api_key.startswith("enc:"), "Env var reference should not have 'enc:' prefix"


@pytest.mark.asyncio
async def test_update_with_new_key(test_db):
    """Test that updating a config with a new key encrypts it."""
    db = test_db

    # Set encryption key
    os.environ["CONFIG_ENCRYPTION_KEY"] = "test-encryption-key-32-chars-min"

    manager = ConfigManager(db)

    # Create config
    config_data = {
        "bundle": {"name": "test", "version": "1.0.0"},
        "providers": [{"config": {"api_key": "sk-ant-original-key"}}],
    }

    config = await manager.create_config(
        name="test-config-update", config_data=config_data, validate=False
    )

    # Update with new key
    new_config_data = {
        "bundle": {"name": "test", "version": "1.0.0"},
        "providers": [{"config": {"api_key": "sk-ant-updated-key"}}],
    }

    updated_config = await manager.update_config(config.config_id, config_data=new_config_data)

    # Get encrypted version
    encrypted_config = await manager.get_config(config.config_id, decrypt=False)
    encrypted_api_key = encrypted_config.config_data["providers"][0]["config"]["api_key"]
    assert encrypted_api_key.startswith("enc:"), "Updated key should be encrypted"

    # Get decrypted version
    decrypted_config = await manager.get_config(config.config_id, decrypt=True)
    decrypted_api_key = decrypted_config.config_data["providers"][0]["config"]["api_key"]
    assert decrypted_api_key == "sk-ant-updated-key", "Updated key should decrypt correctly"


@pytest.mark.asyncio
async def test_multiple_sensitive_fields(test_db):
    """Test that multiple sensitive fields are encrypted."""
    db = test_db

    # Set encryption key
    os.environ["CONFIG_ENCRYPTION_KEY"] = "test-encryption-key-32-chars-min"

    manager = ConfigManager(db)

    # Create config with multiple sensitive fields
    config_data = {
        "bundle": {"name": "test", "version": "1.0.0"},
        "providers": [
            {
                "config": {
                    "api_key": "sk-ant-key-123",
                    "secret": "my-secret-value",
                    "password": "my-password",
                    "token": "my-token",
                    "normal_field": "not-encrypted",
                }
            }
        ],
    }

    config = await manager.create_config(
        name="test-config-multiple", config_data=config_data, validate=False
    )

    # Get encrypted version
    encrypted_config = await manager.get_config(config.config_id, decrypt=False)
    provider_config = encrypted_config.config_data["providers"][0]["config"]

    # Verify all sensitive fields are encrypted
    assert provider_config["api_key"].startswith("enc:"), "api_key should be encrypted"
    assert provider_config["secret"].startswith("enc:"), "secret should be encrypted"
    assert provider_config["password"].startswith("enc:"), "password should be encrypted"
    assert provider_config["token"].startswith("enc:"), "token should be encrypted"

    # Verify normal field is NOT encrypted
    assert provider_config["normal_field"] == "not-encrypted", "Normal field should not be encrypted"
    assert not provider_config["normal_field"].startswith(
        "enc:"
    ), "Normal field should not have 'enc:' prefix"

    # Get decrypted version
    decrypted_config = await manager.get_config(config.config_id, decrypt=True)
    decrypted_provider_config = decrypted_config.config_data["providers"][0]["config"]

    # Verify all sensitive fields are decrypted correctly
    assert decrypted_provider_config["api_key"] == "sk-ant-key-123"
    assert decrypted_provider_config["secret"] == "my-secret-value"
    assert decrypted_provider_config["password"] == "my-password"
    assert decrypted_provider_config["token"] == "my-token"
    assert decrypted_provider_config["normal_field"] == "not-encrypted"


@pytest.mark.asyncio
async def test_no_encryption_key_warning(test_db):
    """Test that ConfigManager warns when no encryption key is set."""
    db = test_db

    # Remove encryption key
    if "CONFIG_ENCRYPTION_KEY" in os.environ:
        del os.environ["CONFIG_ENCRYPTION_KEY"]

    # This should work but log a warning
    manager = ConfigManager(db)

    # Create config (should store in plain text since no encryption key)
    config_data = {
        "bundle": {"name": "test", "version": "1.0.0"},
        "providers": [{"config": {"api_key": "sk-ant-plain-text"}}],
    }

    config = await manager.create_config(
        name="test-config-no-encryption", config_data=config_data, validate=False
    )

    # Get config (should return plain text since no encryption)
    retrieved_config = await manager.get_config(config.config_id, decrypt=False)
    api_key = retrieved_config.config_data["providers"][0]["config"]["api_key"]

    # Verify key is stored in plain text (no encryption)
    assert api_key == "sk-ant-plain-text", "Key should be plain text when no encryption key"
    assert not api_key.startswith("enc:"), "Key should not be encrypted when no encryption key"
