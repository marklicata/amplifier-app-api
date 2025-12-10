"""Tests for provider_manager module."""

import pytest
from unittest.mock import MagicMock, patch
from amplifier_foundation.provider_manager import (
    ProviderManager,
    ProviderInfo,
    ConfigureResult,
    ResetResult,
)


@pytest.fixture
def mock_config():
    """Mock ConfigManager."""
    config = MagicMock()
    config.get_merged_settings.return_value = {}
    return config


@pytest.fixture
def provider_manager(mock_config):
    """Create ProviderManager instance."""
    return ProviderManager(mock_config)


def test_provider_manager_init(mock_config):
    """Test ProviderManager initialization."""
    mgr = ProviderManager(mock_config)
    assert mgr.config == mock_config
    assert mgr._settings is not None


def test_use_provider_with_explicit_source(provider_manager, mock_config):
    """Test configuring provider with explicit source."""
    result = provider_manager.use_provider(
        provider_id="provider-test",
        scope="global",
        config={"model": "test-model"},
        source="git+https://example.com/provider-test",
    )
    
    assert isinstance(result, ConfigureResult)
    assert result.provider == "provider-test"
    assert result.scope == "global"
    assert result.config == {"model": "test-model"}


@patch("amplifier_foundation.provider_manager.get_effective_provider_sources")
def test_use_provider_with_effective_source(mock_get_sources, provider_manager, mock_config):
    """Test configuring provider using effective sources."""
    mock_get_sources.return_value = {
        "provider-test": "git+https://example.com/provider-test"
    }
    
    result = provider_manager.use_provider(
        provider_id="provider-test",
        scope="global",
        config={"model": "test-model"},
    )
    
    assert result.provider == "provider-test"
    mock_get_sources.assert_called_once()


def test_get_current_provider_none(provider_manager, mock_config):
    """Test getting current provider when none configured."""
    mock_config.get_merged_settings.return_value = {}
    
    result = provider_manager.get_current_provider()
    assert result is None


def test_get_current_provider_exists(provider_manager, mock_config):
    """Test getting current provider when one is configured."""
    # Mock settings to return a provider
    provider_manager._settings.get_provider_overrides = MagicMock(return_value=[
        {"module": "provider-test", "config": {"model": "test-model"}}
    ])
    provider_manager._settings.get_scope_provider_overrides = MagicMock(return_value=[])
    
    result = provider_manager.get_current_provider()
    
    assert result is not None
    assert isinstance(result, ProviderInfo)
    assert result.module_id == "provider-test"
    assert result.config == {"model": "test-model"}


def test_get_provider_config_merged(provider_manager):
    """Test getting provider config from merged settings."""
    provider_manager._settings.get_provider_overrides = MagicMock(return_value=[
        {"module": "provider-test", "config": {"model": "test-model"}}
    ])
    
    config = provider_manager.get_provider_config("provider-test")
    
    assert config == {"model": "test-model"}


def test_get_provider_config_scope_specific(provider_manager):
    """Test getting provider config from specific scope."""
    provider_manager._settings.get_scope_provider_overrides = MagicMock(return_value=[
        {"module": "provider-test", "config": {"model": "global-model"}}
    ])
    provider_manager._settings.scope_path = MagicMock(return_value="/path/to/config")
    
    config = provider_manager.get_provider_config("provider-test", scope="global")
    
    assert config == {"model": "global-model"}
    provider_manager._settings.get_scope_provider_overrides.assert_called_once_with("global")


def test_get_provider_config_not_found(provider_manager):
    """Test getting provider config when provider not found."""
    provider_manager._settings.get_provider_overrides = MagicMock(return_value=[])
    
    config = provider_manager.get_provider_config("nonexistent")
    
    assert config is None


def test_reset_provider_success(provider_manager):
    """Test resetting provider override."""
    provider_manager._settings.clear_provider_override = MagicMock(return_value=True)
    
    result = provider_manager.reset_provider("global")
    
    assert isinstance(result, ResetResult)
    assert result.scope == "global"
    assert result.removed is True


def test_reset_provider_nothing_to_remove(provider_manager):
    """Test resetting provider when nothing to remove."""
    provider_manager._settings.clear_provider_override = MagicMock(return_value=False)
    
    result = provider_manager.reset_provider("global")
    
    assert result.scope == "global"
    assert result.removed is False


def test_determine_provider_source_local(provider_manager):
    """Test determining provider source from local scope."""
    provider = {"module": "provider-test"}
    provider_manager._settings.get_scope_provider_overrides = MagicMock(side_effect=[
        [{"module": "provider-test"}],  # local
        [],  # project
        [],  # global
    ])
    
    source = provider_manager._determine_provider_source(provider)
    
    assert source == "local"


def test_determine_provider_source_profile(provider_manager):
    """Test determining provider source from profile."""
    provider = {"module": "provider-test"}
    provider_manager._settings.get_scope_provider_overrides = MagicMock(side_effect=[
        [],  # local
        [],  # project
        [],  # global
    ])
    
    source = provider_manager._determine_provider_source(provider)
    
    assert source == "profile"
