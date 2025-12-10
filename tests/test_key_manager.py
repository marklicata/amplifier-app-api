"""Tests for API key management."""

import os
import tempfile
from pathlib import Path

import pytest

from amplifier_app_utils.key_manager import KeyManager


@pytest.fixture
def temp_home(monkeypatch, tmp_path):
    """Create temporary home directory for testing."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # Clear any existing API keys from environment
    for key in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"]:
        monkeypatch.delenv(key, raising=False)
    return tmp_path


@pytest.fixture
def key_manager(temp_home):
    """Create key manager with temporary home."""
    return KeyManager()


def test_key_manager_init(key_manager, temp_home):
    """Test key manager initialization."""
    assert key_manager.keys_file == temp_home / ".amplifier" / "keys.env"


def test_has_key_from_env(key_manager, monkeypatch):
    """Test checking for key in environment."""
    monkeypatch.setenv("TEST_API_KEY", "test-value")
    assert key_manager.has_key("TEST_API_KEY")
    assert not key_manager.has_key("NONEXISTENT_KEY")


def test_save_and_load_key(key_manager, temp_home):
    """Test saving and loading API keys."""
    # Save a key
    key_manager.save_key("ANTHROPIC_API_KEY", "sk-ant-test123")

    # File should exist
    assert key_manager.keys_file.exists()

    # Should be in environment
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-test123"

    # Create new manager to test loading
    manager2 = KeyManager()

    # Should load into environment
    assert manager2.has_key("ANTHROPIC_API_KEY")


def test_save_multiple_keys(key_manager):
    """Test saving multiple keys."""
    key_manager.save_key("OPENAI_API_KEY", "sk-test-openai")
    key_manager.save_key("ANTHROPIC_API_KEY", "sk-test-anthropic")

    # Both should be present
    assert key_manager.has_key("OPENAI_API_KEY")
    assert key_manager.has_key("ANTHROPIC_API_KEY")

    # Check file contents
    content = key_manager.keys_file.read_text()
    assert "OPENAI_API_KEY" in content
    assert "ANTHROPIC_API_KEY" in content


def test_update_existing_key(key_manager):
    """Test updating an existing key."""
    # Save initial value
    key_manager.save_key("TEST_KEY", "old-value")
    assert os.environ["TEST_KEY"] == "old-value"

    # Update value
    key_manager.save_key("TEST_KEY", "new-value")
    assert os.environ["TEST_KEY"] == "new-value"

    # File should only have one entry
    content = key_manager.keys_file.read_text()
    assert content.count("TEST_KEY") == 1


def test_get_configured_provider(key_manager, monkeypatch):
    """Test detecting configured provider."""
    # No provider configured
    assert key_manager.get_configured_provider() is None

    # Anthropic configured
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert key_manager.get_configured_provider() == "anthropic"

    # Clear and test OpenAI
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert key_manager.get_configured_provider() == "openai"

    # Clear and test Azure
    monkeypatch.delenv("OPENAI_API_KEY")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
    assert key_manager.get_configured_provider() == "azure"


def test_keys_file_secure_permissions(key_manager, temp_home):
    """Test that keys file has secure permissions (Unix only)."""
    import platform

    if platform.system() == "Windows":
        pytest.skip("Permission checking not applicable on Windows")

    key_manager.save_key("TEST_KEY", "test-value")

    # Check file permissions (should be 0o600 = owner read/write only)
    stat = key_manager.keys_file.stat()
    mode = stat.st_mode & 0o777
    assert mode == 0o600
