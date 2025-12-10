"""Tests for PathManager."""

import pytest
from pathlib import Path
from amplifier_app_utils.paths import PathManager


def test_path_manager_defaults():
    """Test PathManager with default settings."""
    pm = PathManager()
    
    assert pm.app_name == "amplifier"
    assert pm.user_dir == Path.home() / ".amplifier"
    assert pm.project_dir == Path(".amplifier")
    

def test_path_manager_custom():
    """Test PathManager with custom settings."""
    pm = PathManager(
        user_dir="~/.my-app",
        project_dir=".my-app",
        app_name="my-app"
    )
    
    assert pm.app_name == "my-app"
    assert pm.user_dir == Path.home() / ".my-app"
    assert pm.project_dir == Path(".my-app")


def test_config_paths():
    """Test config paths generation."""
    pm = PathManager()
    config_paths = pm.get_config_paths()
    
    assert config_paths.user == pm.user_dir / "settings.yaml"
    # Project and local depend on whether we're in home dir
    

def test_collection_search_paths():
    """Test collection search paths."""
    pm = PathManager()
    paths = pm.get_collection_search_paths()
    
    assert len(paths) == 3
    assert paths[0] == Path.cwd() / pm.project_dir / "collections"
    assert paths[1] == pm.user_dir / "collections"
    assert paths[2] == pm.bundled_dir / "collections"


def test_workspace_dir():
    """Test workspace directory."""
    pm = PathManager()
    workspace = pm.get_workspace_dir()
    
    assert workspace == pm.project_dir / "modules"


def test_session_dir():
    """Test session directory."""
    pm = PathManager()
    session_dir = pm.get_session_dir()
    
    assert session_dir == pm.user_dir / "sessions"


def test_keys_file():
    """Test keys file path."""
    pm = PathManager()
    keys_file = pm.get_keys_file()
    
    assert keys_file == pm.user_dir / "keys.enc"
