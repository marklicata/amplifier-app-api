"""Tests for module_manager module."""

import pytest
from unittest.mock import MagicMock
from pathlib import Path
from amplifier_config import Scope
from amplifier_app_utils.module_manager import ModuleManager, AddModuleResult


@pytest.fixture
def mock_config():
    """Mock ConfigManager."""
    config = MagicMock()
    config.scope_to_path = MagicMock(return_value=Path("/tmp/user.yaml"))
    config._read_yaml = MagicMock(return_value={})
    config._write_yaml = MagicMock()
    return config


@pytest.fixture
def module_manager(mock_config):
    """Create ModuleManager instance."""
    return ModuleManager(mock_config)


def test_module_manager_init(mock_config):
    """Test ModuleManager initialization."""
    manager = ModuleManager(mock_config)
    assert manager.settings == mock_config


def test_add_module_basic(module_manager, mock_config):
    """Test adding a basic module."""
    mock_config._read_yaml.return_value = {}
    mock_config.paths = MagicMock()
    mock_config.paths.user = Path("/tmp/user.yaml")
    
    result = module_manager.add_module(
        module_id="tool-shell",
        module_type="tool",
        scope="global"
    )
    
    assert result.module_id == "tool-shell"
    assert result.module_type == "tool"
    assert result.scope == "global"
    # Check the path uses backslash or forward slash depending on OS
    assert "user.yaml" in result.file.replace("\\", "/")
    
    # Verify write was called with proper structure
    mock_config._write_yaml.assert_called_once()
    call_args = mock_config._write_yaml.call_args
    written_data = call_args[0][1]
    assert "modules" in written_data
    assert "tools" in written_data["modules"]
    assert any(m["module"] == "tool-shell" for m in written_data["modules"]["tools"])


def test_add_module_with_source_and_config(module_manager, mock_config):
    """Test adding module with source and config."""
    mock_config._read_yaml.return_value = {}
    mock_config.paths = MagicMock()
    mock_config.paths.user = Path("/tmp/user.yaml")
    
    result = module_manager.add_module(
        module_id="provider-custom",
        module_type="provider",
        source="git+https://github.com/example/provider",
        config={"api_key": "test-key"},
        scope="global"
    )
    
    assert result.module_id == "provider-custom"
    assert result.module_type == "provider"
    
    # Verify write includes source and config
    call_args = mock_config._write_yaml.call_args
    written_data = call_args[0][1]
    provider = written_data["modules"]["providers"][0]
    assert provider["module"] == "provider-custom"
    assert provider["source"] == "git+https://github.com/example/provider"
    assert provider["config"] == {"api_key": "test-key"}


def test_add_module_prevents_duplicates(module_manager, mock_config):
    """Test that adding duplicate module is prevented."""
    mock_config._read_yaml.return_value = {
        "modules": {
            "tools": [{"module": "tool-shell"}]
        }
    }
    mock_config.paths = MagicMock()
    mock_config.paths.user = Path("/tmp/user.yaml")
    
    result = module_manager.add_module(
        module_id="tool-shell",
        module_type="tool",
        scope="global"
    )
    
    # Should still succeed but not add duplicate
    assert result.module_id == "tool-shell"
    
    # Verify write was NOT called since it's a duplicate
    mock_config._write_yaml.assert_not_called()


def test_add_module_different_types(module_manager, mock_config):
    """Test adding modules of different types."""
    mock_config._read_yaml.return_value = {}
    
    # Add multiple module types
    module_manager.add_module("tool-shell", "tool", scope="global")
    module_manager.add_module("hook-logger", "hook", scope="global")
    module_manager.add_module("agent-coder", "agent", scope="global")
    
    # Verify all written
    assert mock_config._write_yaml.call_count == 3


def test_remove_module(module_manager, mock_config):
    """Test removing a module."""
    mock_config._read_yaml.return_value = {
        "modules": {
            "tools": [
                {"module": "tool-shell"},
                {"module": "tool-git"}
            ]
        }
    }
    mock_config.paths = MagicMock()
    mock_config.paths.user = Path("/tmp/user.yaml")
    
    result = module_manager.remove_module("tool-shell", scope="global")
    
    assert result.module_id == "tool-shell"
    assert result.scope == "global"
    
    # Verify removal
    call_args = mock_config._write_yaml.call_args
    written_data = call_args[0][1]
    assert "tool-shell" not in [m["module"] for m in written_data["modules"]["tools"]]
    assert "tool-git" in [m["module"] for m in written_data["modules"]["tools"]]


def test_remove_module_cleans_up_empty_sections(module_manager, mock_config):
    """Test that removing last module removes empty section."""
    mock_config._read_yaml.return_value = {
        "modules": {
            "tools": [{"module": "tool-shell"}]
        },
        "other_config": "value"
    }
    mock_config.paths = MagicMock()
    mock_config.paths.user = Path("/tmp/user.yaml")
    
    result = module_manager.remove_module("tool-shell", scope="global")
    
    assert result.module_id == "tool-shell"
    assert result.scope == "global"
    
    # Verify empty section is removed but other config preserved
    call_args = mock_config._write_yaml.call_args
    written_data = call_args[0][1]
    assert "modules" not in written_data
    assert written_data["other_config"] == "value"


def test_remove_module_not_found(module_manager, mock_config):
    """Test removing a module that doesn't exist."""
    mock_config._read_yaml.return_value = {
        "modules": {
            "tools": [{"module": "tool-git"}]
        }
    }
    mock_config.paths = MagicMock()
    mock_config.paths.user = Path("/tmp/user.yaml")
    
    result = module_manager.remove_module("tool-shell", scope="global")
    
    # Module should still have info even if not found
    assert result.module_id == "tool-shell"
    assert result.scope == "global"


def test_get_current_modules_empty(module_manager, mock_config):
    """Test getting modules when none exist."""
    mock_config.get_merged_settings.return_value = {}
    
    modules = module_manager.get_current_modules()
    
    assert modules == []


def test_get_current_modules_various_types(module_manager, mock_config):
    """Test getting modules of various types."""
    mock_config.get_merged_settings.return_value = {
        "modules": {
            "tools": [
                {"module": "tool-shell"},
                {"module": "tool-git"}
            ],
            "hooks": [
                {"module": "hook-logger"}
            ],
            "providers": [
                {"module": "provider-anthropic"}
            ]
        }
    }
    
    # Get all modules
    modules = module_manager.get_current_modules()
    assert len(modules) == 4
    
    # Check we have the right types
    module_ids = [m.module_id for m in modules]
    assert "tool-shell" in module_ids
    assert "tool-git" in module_ids
    assert "hook-logger" in module_ids
    assert "provider-anthropic" in module_ids


def test_get_file_for_scope(module_manager, mock_config):
    """Test getting config file path for different scopes."""
    mock_config.paths = MagicMock()
    mock_config.paths.local = Path("/tmp/local.yaml")
    mock_config.paths.project = Path("/tmp/project.yaml")
    mock_config.paths.user = Path("/tmp/user.yaml")
    
    path = module_manager._get_file_for_scope("local")
    assert path == Path("/tmp/local.yaml")
    
    path = module_manager._get_file_for_scope("project")
    assert path == Path("/tmp/project.yaml")
    
    path = module_manager._get_file_for_scope("user")
    assert path == Path("/tmp/user.yaml")
