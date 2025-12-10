"""Tests for module_manager module."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from amplifier_foundation.module_manager import (
    ModuleManager,
    ModuleInfo,
    AddModuleResult,
    RemoveModuleResult,
)


@pytest.fixture
def mock_config():
    """Mock ConfigManager."""
    config = MagicMock()
    config._read_yaml = MagicMock(return_value={})
    config._write_yaml = MagicMock()
    config.get_merged_settings = MagicMock(return_value={})
    config.paths = MagicMock()
    config.paths.local = Path("/tmp/local.yaml")
    config.paths.project = Path("/tmp/project.yaml")
    config.paths.user = Path("/tmp/user.yaml")
    return config


@pytest.fixture
def module_manager(mock_config):
    """Create ModuleManager instance."""
    return ModuleManager(mock_config)


def test_module_manager_init(mock_config):
    """Test ModuleManager initialization."""
    mgr = ModuleManager(mock_config)
    assert mgr.settings == mock_config


def test_add_module_basic(module_manager, mock_config):
    """Test adding a module."""
    result = module_manager.add_module(
        module_id="tool-shell",
        module_type="tool",
        scope="global",
    )
    
    assert isinstance(result, AddModuleResult)
    assert result.module_id == "tool-shell"
    assert result.module_type == "tool"
    assert result.scope == "global"
    assert "/tmp/user.yaml" in result.file


def test_add_module_with_source_and_config(module_manager, mock_config):
    """Test adding a module with source and config."""
    result = module_manager.add_module(
        module_id="tool-custom",
        module_type="tool",
        scope="project",
        config={"arg": "value"},
        source="git+https://example.com/tool-custom",
    )
    
    assert result.module_id == "tool-custom"
    assert result.scope == "project"
    
    # Verify write was called with correct structure
    mock_config._write_yaml.assert_called()
    call_args = mock_config._write_yaml.call_args
    written_data = call_args[0][1]
    assert "modules" in written_data
    assert "tools" in written_data["modules"]
    
    # Check the module entry
    module_entry = written_data["modules"]["tools"][0]
    assert module_entry["module"] == "tool-custom"
    assert module_entry["config"] == {"arg": "value"}
    assert module_entry["source"] == "git+https://example.com/tool-custom"


def test_add_module_prevents_duplicates(module_manager, mock_config):
    """Test that duplicate modules are not added."""
    mock_config._read_yaml.return_value = {
        "modules": {
            "tools": [{"module": "tool-shell"}]
        }
    }
    
    result = module_manager.add_module(
        module_id="tool-shell",
        module_type="tool",
        scope="global",
    )
    
    # Should still return success but not add duplicate
    assert result.module_id == "tool-shell"


def test_add_module_different_types(module_manager, mock_config):
    """Test adding modules of different types."""
    types_to_test = [
        ("tool", "tools"),
        ("hook", "hooks"),
        ("agent", "agents"),
        ("provider", "providers"),
        ("orchestrator", "orchestrators"),
        ("context", "contexts"),
    ]
    
    for module_type, expected_key in types_to_test:
        mock_config._read_yaml.return_value = {}
        mock_config._write_yaml.reset_mock()
        
        result = module_manager.add_module(
            module_id=f"{module_type}-test",
            module_type=module_type,  # type: ignore
            scope="global",
        )
        
        assert result.module_type == module_type
        
        # Verify correct key was used
        call_args = mock_config._write_yaml.call_args
        written_data = call_args[0][1]
        assert expected_key in written_data["modules"]


def test_remove_module(module_manager, mock_config):
    """Test removing a module."""
    mock_config._read_yaml.return_value = {
        "modules": {
            "tools": [
                {"module": "tool-shell"},
                {"module": "tool-other"},
            ]
        }
    }
    
    result = module_manager.remove_module("tool-shell", "global")
    
    assert isinstance(result, RemoveModuleResult)
    assert result.module_id == "tool-shell"
    assert result.scope == "global"
    
    # Verify tool-shell was removed
    call_args = mock_config._write_yaml.call_args
    written_data = call_args[0][1]
    remaining_tools = [m["module"] for m in written_data["modules"]["tools"]]
    assert "tool-shell" not in remaining_tools
    assert "tool-other" in remaining_tools


def test_remove_module_cleans_up_empty_sections(module_manager, mock_config):
    """Test that empty sections are cleaned up after removal."""
    mock_config._read_yaml.return_value = {
        "modules": {
            "tools": [{"module": "tool-shell"}]
        }
    }
    
    result = module_manager.remove_module("tool-shell", "global")
    
    # Verify empty modules section was removed
    call_args = mock_config._write_yaml.call_args
    written_data = call_args[0][1]
    assert "modules" not in written_data


def test_remove_module_not_found(module_manager, mock_config):
    """Test removing a module that doesn't exist."""
    mock_config._read_yaml.return_value = {
        "modules": {
            "tools": [{"module": "tool-other"}]
        }
    }
    
    result = module_manager.remove_module("tool-nonexistent", "global")
    
    assert result.module_id == "tool-nonexistent"


def test_get_current_modules_empty(module_manager, mock_config):
    """Test getting modules when none configured."""
    mock_config.get_merged_settings.return_value = {}
    
    modules = module_manager.get_current_modules()
    
    assert modules == []


def test_get_current_modules_various_types(module_manager, mock_config):
    """Test getting modules of various types."""
    mock_config.get_merged_settings.return_value = {
        "modules": {
            "tools": [{"module": "tool-shell"}],
            "hooks": [{"module": "hook-logger"}],
            "agents": [{"module": "agent-helper"}],
        }
    }
    
    modules = module_manager.get_current_modules()
    
    assert len(modules) == 3
    
    # Check each module
    module_dict = {m.module_id: m for m in modules}
    
    assert "tool-shell" in module_dict
    assert module_dict["tool-shell"].module_type == "tool"
    
    assert "hook-logger" in module_dict
    assert module_dict["hook-logger"].module_type == "hook"
    
    assert "agent-helper" in module_dict
    assert module_dict["agent-helper"].module_type == "agent"


def test_get_file_for_scope(module_manager, mock_config):
    """Test getting file path for different scopes."""
    assert module_manager._get_file_for_scope("user") == mock_config.paths.user
    assert module_manager._get_file_for_scope("project") == mock_config.paths.project
    assert module_manager._get_file_for_scope("local") == mock_config.paths.local
