"""Tests for provider sources module."""

import pytest

from amplifier_app_utils.provider_sources import (
    DEFAULT_PROVIDER_SOURCES,
    get_effective_provider_sources,
    is_local_path,
    source_from_uri,
)


def test_default_provider_sources():
    """Test default provider sources are defined."""
    assert "provider-anthropic" in DEFAULT_PROVIDER_SOURCES
    assert "provider-openai" in DEFAULT_PROVIDER_SOURCES
    assert "provider-azure-openai" in DEFAULT_PROVIDER_SOURCES
    assert "provider-ollama" in DEFAULT_PROVIDER_SOURCES

    # Check they're all git URLs
    for module_id, source in DEFAULT_PROVIDER_SOURCES.items():
        assert source.startswith("git+https://")


def test_is_local_path():
    """Test local path detection."""
    # Local paths
    assert is_local_path("/absolute/path")
    assert is_local_path("./relative/path")
    assert is_local_path("../parent/path")
    assert is_local_path("file:///path/to/file")

    # Git URLs
    assert not is_local_path("git+https://github.com/user/repo")
    assert not is_local_path("https://example.com")
    assert not is_local_path("some-module-name")


def test_source_from_uri_local():
    """Test source_from_uri with local paths."""
    from amplifier_module_resolution.sources import FileSource

    source = source_from_uri("./local/path")
    assert isinstance(source, FileSource)

    source = source_from_uri("/absolute/path")
    assert isinstance(source, FileSource)


def test_source_from_uri_git():
    """Test source_from_uri with git URLs."""
    from amplifier_module_resolution.sources import GitSource

    source = source_from_uri("git+https://github.com/user/repo@main")
    assert isinstance(source, GitSource)


def test_get_effective_provider_sources_no_config():
    """Test getting effective sources without config manager."""
    sources = get_effective_provider_sources(None)

    # Should return defaults
    assert sources == DEFAULT_PROVIDER_SOURCES


def test_get_effective_provider_sources_with_overrides():
    """Test getting effective sources with config manager overrides."""
    # Mock config manager
    class MockConfigManager:
        def get_module_sources(self):
            return {"provider-anthropic": "git+https://custom.repo/anthropic@dev"}

        def get_merged_settings(self):
            return {}

    config = MockConfigManager()
    sources = get_effective_provider_sources(config)

    # Should have override for anthropic
    assert sources["provider-anthropic"] == "git+https://custom.repo/anthropic@dev"

    # Others should be default
    assert sources["provider-openai"] == DEFAULT_PROVIDER_SOURCES["provider-openai"]


def test_get_effective_provider_sources_with_user_added():
    """Test getting effective sources with user-added providers."""

    class MockConfigManager:
        def get_module_sources(self):
            return {}

        def get_merged_settings(self):
            return {
                "modules": {
                    "providers": [
                        {"module": "provider-custom", "source": "git+https://custom.repo/provider@main"},
                    ]
                }
            }

    config = MockConfigManager()
    sources = get_effective_provider_sources(config)

    # Should include user-added provider
    assert "provider-custom" in sources
    assert sources["provider-custom"] == "git+https://custom.repo/provider@main"

    # Should still have defaults
    assert "provider-anthropic" in sources
