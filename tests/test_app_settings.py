"""Tests for app_settings module."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from amplifier_config import Scope
from amplifier_foundation.app_settings import AppSettings, ScopeType, _SCOPE_MAP


@pytest.fixture
def mock_config():
    """Mock ConfigManager."""
    config = MagicMock()
    config.scope_to_path = MagicMock(return_value=Path("/tmp/config.yaml"))
    config.get_merged_settings = MagicMock(return_value={})
    config._read_yaml = MagicMock(return_value={})
    config._write_yaml = MagicMock()
    return config


@pytest.fixture
def app_settings(mock_config):
    """Create AppSettings instance."""
    return AppSettings(mock_config)


def test_app_settings_init(mock_config):
    """Test AppSettings initialization."""
    settings = AppSettings(mock_config)
    assert settings._config == mock_config


def test_scope_enum_mapping():
    """Test scope type to enum mapping."""
    assert _SCOPE_MAP["local"] == Scope.LOCAL
    assert _SCOPE_MAP["project"] == Scope.PROJECT
    assert _SCOPE_MAP["global"] == Scope.USER


def test_scope_enum(app_settings):
    """Test _scope_enum conversion."""
    assert app_settings._scope_enum("local") == Scope.LOCAL
    assert app_settings._scope_enum("project") == Scope.PROJECT
    assert app_settings._scope_enum("global") == Scope.USER


def test_scope_path(app_settings, mock_config):
    """Test getting scope path."""
    mock_config.scope_to_path.return_value = Path("/tmp/local.yaml")
    
    path = app_settings.scope_path("local")
    
    assert path == Path("/tmp/local.yaml")
    mock_config.scope_to_path.assert_called_once_with(Scope.LOCAL)


def test_set_provider_override(app_settings, mock_config):
    """Test setting provider override."""
    provider_entry = {
        "module": "provider-test",
        "config": {"model": "test-model"}
    }
    
    app_settings.set_provider_override(provider_entry, "global")
    
    mock_config.update_settings.assert_called_once()
    call_args = mock_config.update_settings.call_args
    assert call_args[0][0] == {"config": {"providers": [provider_entry]}}
    assert call_args[1]["scope"] == Scope.USER


def test_clear_provider_override_success(app_settings, mock_config):
    """Test clearing provider override when providers exist."""
    mock_config._read_yaml.return_value = {
        "config": {
            "providers": [{"module": "provider-test"}]
        }
    }
    
    result = app_settings.clear_provider_override("global")
    
    assert result is True
    mock_config._write_yaml.assert_called_once()


def test_clear_provider_override_nothing_to_clear(app_settings, mock_config):
    """Test clearing provider override when nothing to clear."""
    mock_config._read_yaml.return_value = {}
    
    result = app_settings.clear_provider_override("global")
    
    assert result is False


def test_clear_provider_override_preserves_other_config(app_settings, mock_config):
    """Test that clearing provider preserves other config sections."""
    mock_config._read_yaml.return_value = {
        "config": {
            "providers": [{"module": "provider-test"}],
            "other_setting": "value"
        }
    }
    
    result = app_settings.clear_provider_override("global")
    
    assert result is True
    call_args = mock_config._write_yaml.call_args
    written_data = call_args[0][1]
    assert "providers" not in written_data["config"]
    assert written_data["config"]["other_setting"] == "value"


def test_get_provider_overrides(app_settings, mock_config):
    """Test getting merged provider overrides."""
    mock_config.get_merged_settings.return_value = {
        "config": {
            "providers": [
                {"module": "provider-test", "config": {"model": "test-model"}}
            ]
        }
    }
    
    providers = app_settings.get_provider_overrides()
    
    assert len(providers) == 1
    assert providers[0]["module"] == "provider-test"


def test_get_provider_overrides_empty(app_settings, mock_config):
    """Test getting provider overrides when none exist."""
    mock_config.get_merged_settings.return_value = {}
    
    providers = app_settings.get_provider_overrides()
    
    assert providers == []


def test_get_scope_provider_overrides(app_settings, mock_config):
    """Test getting provider overrides from specific scope."""
    mock_config._read_yaml.return_value = {
        "config": {
            "providers": [
                {"module": "provider-global", "config": {"model": "global-model"}}
            ]
        }
    }
    
    providers = app_settings.get_scope_provider_overrides("global")
    
    assert len(providers) == 1
    assert providers[0]["module"] == "provider-global"


def test_get_scope_provider_overrides_empty(app_settings, mock_config):
    """Test getting scope provider overrides when none exist."""
    mock_config._read_yaml.return_value = {}
    
    providers = app_settings.get_scope_provider_overrides("global")
    
    assert providers == []


@patch("amplifier_foundation.app_settings.DEFAULT_PROVIDER_SOURCES")
def test_apply_provider_overrides_to_profile(mock_sources, app_settings, mock_config):
    """Test applying provider overrides to profile."""
    from amplifier_profiles.schema import Profile, ModuleConfig
    
    mock_sources.get.return_value = "git+https://example.com/provider-test"
    
    # Create base profile with one provider
    profile = Profile(
        name="test-profile",
        providers=[
            ModuleConfig(module="provider-test", config={"model": "base-model"})
        ]
    )
    
    # Override with different model
    overrides = [
        {"module": "provider-test", "config": {"model": "override-model"}}
    ]
    
    result = app_settings.apply_provider_overrides_to_profile(profile, overrides)
    
    # Check that override was applied
    assert len(result.providers) == 1
    assert result.providers[0].module == "provider-test"
    assert result.providers[0].config["model"] == "override-model"


@patch("amplifier_foundation.app_settings.DEFAULT_PROVIDER_SOURCES")
def test_apply_provider_overrides_adds_new_provider(mock_sources, app_settings, mock_config):
    """Test that applying overrides can add new providers."""
    from amplifier_profiles.schema import Profile, ModuleConfig
    
    mock_sources.get.return_value = "git+https://example.com/provider-new"
    
    # Create base profile with one provider
    profile = Profile(
        name="test-profile",
        providers=[
            ModuleConfig(module="provider-existing", config={"model": "existing"})
        ]
    )
    
    # Add a new provider via override
    overrides = [
        {"module": "provider-new", "config": {"model": "new-model"}}
    ]
    
    result = app_settings.apply_provider_overrides_to_profile(profile, overrides)
    
    # Check that both providers exist
    assert len(result.providers) == 2
    module_ids = [p.module for p in result.providers]
    assert "provider-existing" in module_ids
    assert "provider-new" in module_ids


def test_apply_provider_overrides_no_overrides(app_settings):
    """Test applying overrides when there are none."""
    from amplifier_profiles.schema import Profile, ModuleConfig
    
    profile = Profile(
        name="test-profile",
        providers=[
            ModuleConfig(module="provider-test", config={"model": "base-model"})
        ]
    )
    
    result = app_settings.apply_provider_overrides_to_profile(profile, [])
    
    # Should return original profile unchanged
    assert result == profile
