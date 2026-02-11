"""Tests for config secrets encryption."""

import os

import pytest

from amplifier_app_api.core.secrets_encryption import ConfigEncryption


@pytest.fixture
def encryption():
    """Create encryption instance with test key."""
    test_key = "test-encryption-key-for-testing"
    return ConfigEncryption(test_key)


def test_encrypt_api_key(encryption):
    """Test that API keys are encrypted."""
    config = {
        "providers": [
            {
                "module": "provider-anthropic",
                "config": {"api_key": "sk-ant-1234567890", "model": "claude-sonnet-4-5"},
            }
        ]
    }

    encrypted = encryption.encrypt_config(config)

    # Check that api_key is encrypted (has enc: prefix)
    assert encrypted["providers"][0]["config"]["api_key"].startswith("enc:")
    # Check that model is NOT encrypted
    assert encrypted["providers"][0]["config"]["model"] == "claude-sonnet-4-5"


def test_decrypt_api_key(encryption):
    """Test that encrypted API keys are decrypted correctly."""
    original_key = "sk-ant-1234567890"
    config = {"providers": [{"module": "provider-anthropic", "config": {"api_key": original_key}}]}

    # Encrypt then decrypt
    encrypted = encryption.encrypt_config(config)
    decrypted = encryption.decrypt_config(encrypted)

    # Should match original
    assert decrypted["providers"][0]["config"]["api_key"] == original_key


def test_env_var_references_not_encrypted(encryption):
    """Test that environment variable references are not encrypted."""
    config = {
        "providers": [
            {
                "module": "provider-anthropic",
                "config": {"api_key": "${ANTHROPIC_API_KEY}", "model": "claude-sonnet-4-5"},
            }
        ]
    }

    encrypted = encryption.encrypt_config(config)

    # Env var reference should remain unchanged
    assert encrypted["providers"][0]["config"]["api_key"] == "${ANTHROPIC_API_KEY}"


def test_multiple_sensitive_fields(encryption):
    """Test encryption of multiple sensitive field types."""
    config = {
        "auth": {
            "api_key": "key123",
            "secret": "secret456",
            "password": "pass789",
            "token": "token101",
            "private_key": "pk_xyz",
        },
        "non_sensitive": {"model": "gpt-4", "temperature": 0.7},
    }

    encrypted = encryption.encrypt_config(config)

    # All sensitive fields should be encrypted
    assert encrypted["auth"]["api_key"].startswith("enc:")
    assert encrypted["auth"]["secret"].startswith("enc:")
    assert encrypted["auth"]["password"].startswith("enc:")
    assert encrypted["auth"]["token"].startswith("enc:")
    assert encrypted["auth"]["private_key"].startswith("enc:")

    # Non-sensitive fields should not be encrypted
    assert encrypted["non_sensitive"]["model"] == "gpt-4"
    assert encrypted["non_sensitive"]["temperature"] == 0.7

    # Decrypt and verify all fields match
    decrypted = encryption.decrypt_config(encrypted)
    assert decrypted["auth"]["api_key"] == "key123"
    assert decrypted["auth"]["secret"] == "secret456"
    assert decrypted["auth"]["password"] == "pass789"
    assert decrypted["auth"]["token"] == "token101"
    assert decrypted["auth"]["private_key"] == "pk_xyz"


def test_already_encrypted_not_double_encrypted(encryption):
    """Test that already encrypted values are not encrypted again."""
    config = {"auth": {"api_key": "enc:already_encrypted_value"}}

    encrypted = encryption.encrypt_config(config)

    # Should remain the same
    assert encrypted["auth"]["api_key"] == "enc:already_encrypted_value"


def test_nested_config_encryption(encryption):
    """Test encryption works with deeply nested configs."""
    config = {
        "providers": [
            {
                "name": "openai",
                "config": {"api_key": "sk-123", "organization": "org-456"},
            },
            {
                "name": "anthropic",
                "config": {"api_key": "sk-ant-789", "timeout": 30},
            },
        ]
    }

    encrypted = encryption.encrypt_config(config)

    # Both API keys should be encrypted
    assert encrypted["providers"][0]["config"]["api_key"].startswith("enc:")
    assert encrypted["providers"][1]["config"]["api_key"].startswith("enc:")

    # Non-sensitive fields should not be encrypted
    assert encrypted["providers"][0]["config"]["organization"] == "org-456"
    assert encrypted["providers"][1]["config"]["timeout"] == 30

    # Decrypt and verify
    decrypted = encryption.decrypt_config(encrypted)
    assert decrypted["providers"][0]["config"]["api_key"] == "sk-123"
    assert decrypted["providers"][1]["config"]["api_key"] == "sk-ant-789"


def test_empty_values_not_encrypted(encryption):
    """Test that empty string values are not encrypted."""
    config = {"auth": {"api_key": "", "secret": None}}

    encrypted = encryption.encrypt_config(config)

    # Empty string should remain empty (not encrypted)
    assert encrypted["auth"]["api_key"] == ""
    # None should remain None
    assert encrypted["auth"]["secret"] is None


def test_encryption_key_from_env():
    """Test that encryption key can be loaded from environment."""
    # Set test key in environment
    os.environ["CONFIG_ENCRYPTION_KEY"] = "test-key-from-env"

    try:
        encryption = ConfigEncryption()
        config = {"auth": {"api_key": "test-key-123"}}

        encrypted = encryption.encrypt_config(config)
        assert encrypted["auth"]["api_key"].startswith("enc:")

        decrypted = encryption.decrypt_config(encrypted)
        assert decrypted["auth"]["api_key"] == "test-key-123"
    finally:
        # Clean up
        del os.environ["CONFIG_ENCRYPTION_KEY"]


def test_missing_encryption_key_raises():
    """Test that missing encryption key raises an error."""
    # Make sure env var is not set
    os.environ.pop("CONFIG_ENCRYPTION_KEY", None)

    with pytest.raises(ValueError, match="CONFIG_ENCRYPTION_KEY.*must be set"):
        ConfigEncryption()


def test_case_insensitive_field_detection(encryption):
    """Test that sensitive field detection is case-insensitive."""
    config = {
        "auth": {
            "API_KEY": "key1",
            "Api_Key": "key2",
            "api_KEY": "key3",
            "SECRET_TOKEN": "token1",
        }
    }

    encrypted = encryption.encrypt_config(config)

    # All variations should be encrypted
    assert encrypted["auth"]["API_KEY"].startswith("enc:")
    assert encrypted["auth"]["Api_Key"].startswith("enc:")
    assert encrypted["auth"]["api_KEY"].startswith("enc:")
    assert encrypted["auth"]["SECRET_TOKEN"].startswith("enc:")
