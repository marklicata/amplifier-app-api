"""Comprehensive tests for ConfigManager.

Tests config management, registries, and helper methods.
"""

import pytest

from amplifier_app_api.core.config_manager import ConfigManager


@pytest.mark.asyncio
class TestConfigManagerHelpers:
    """Test helper methods for YAML parsing and manipulation."""

    async def test_parse_yaml_valid(self, test_db):
        """Test parsing valid YAML."""
        manager = ConfigManager(test_db)
        yaml_content = """
bundle:
  name: test
  version: 1.0.0
providers:
  - module: provider-anthropic
"""
        result = manager.parse_yaml(yaml_content)
        assert isinstance(result, dict)
        assert result["bundle"]["name"] == "test"
        assert len(result["providers"]) == 1

    async def test_parse_yaml_empty_string(self, test_db):
        """Test parsing empty YAML returns empty dict."""
        manager = ConfigManager(test_db)
        result = manager.parse_yaml("")
        assert result == {}

    async def test_parse_yaml_invalid_syntax(self, test_db):
        """Test parsing invalid YAML raises ValueError."""
        manager = ConfigManager(test_db)
        with pytest.raises(ValueError, match="Invalid YAML"):
            manager.parse_yaml("bundle:\n  name: test\n    invalid: indentation")

    async def test_dump_yaml_simple_dict(self, test_db):
        """Test dumping dict to YAML."""
        manager = ConfigManager(test_db)
        data = {
            "bundle": {"name": "test", "version": "1.0.0"},
            "providers": [{"module": "provider-anthropic"}],
        }
        result = manager.dump_yaml(data)
        assert isinstance(result, str)
        assert "bundle:" in result
        assert "name: test" in result
        assert "providers:" in result

    async def test_parse_then_dump_roundtrip(self, test_db):
        """Test that parse -> dump -> parse is lossless."""
        manager = ConfigManager(test_db)
        original_yaml = """
bundle:
  name: roundtrip-test
  version: 2.0.0
providers:
  - module: provider-anthropic
    config:
      model: claude-sonnet-4-5
"""
        parsed = manager.parse_yaml(original_yaml)
        dumped = manager.dump_yaml(parsed)
        reparsed = manager.parse_yaml(dumped)

        assert parsed == reparsed


@pytest.mark.asyncio
class TestBundleRegistryOperations:
    """Test bundle registry management."""

    async def test_list_bundles_empty(self, test_db):
        """Test listing bundles returns a dict (may have data from other tests)."""
        manager = ConfigManager(test_db)
        bundles = await manager.list_bundles()
        assert isinstance(bundles, dict)  # May not be empty if other tests ran

    async def test_add_bundle(self, test_db):
        """Test adding a bundle to registry."""
        manager = ConfigManager(test_db)
        await manager.add_bundle(
            name="test-bundle",
            source="git+https://github.com/example/test-bundle",
            scope="global",
        )

        bundles = await manager.list_bundles()
        assert "test-bundle" in bundles
        assert bundles["test-bundle"]["source"] == "git+https://github.com/example/test-bundle"
        assert bundles["test-bundle"]["scope"] == "global"

    async def test_add_multiple_bundles(self, test_db):
        """Test adding multiple bundles."""
        manager = ConfigManager(test_db)

        await manager.add_bundle(
            name="bundle-1",
            source="git+https://github.com/example/bundle-1",
        )
        await manager.add_bundle(
            name="bundle-2",
            source="git+https://github.com/example/bundle-2",
        )

        bundles = await manager.list_bundles()
        # Other tests may have added bundles - just check ours exist
        assert "bundle-1" in bundles
        assert "bundle-2" in bundles
        assert bundles["bundle-1"]["source"] == "git+https://github.com/example/bundle-1"
        assert bundles["bundle-2"]["source"] == "git+https://github.com/example/bundle-2"

    async def test_remove_bundle(self, test_db):
        """Test removing a bundle from registry."""
        manager = ConfigManager(test_db)

        await manager.add_bundle(name="remove-test", source="test-source")
        success = await manager.remove_bundle("remove-test")

        assert success is True

        bundles = await manager.list_bundles()
        assert "remove-test" not in bundles

    async def test_remove_nonexistent_bundle(self, test_db):
        """Test removing bundle that doesn't exist."""
        manager = ConfigManager(test_db)
        success = await manager.remove_bundle("nonexistent")
        assert success is False

    async def test_get_active_bundle_none_set(self, test_db):
        """Test getting active bundle when none set."""
        manager = ConfigManager(test_db)
        active = await manager.get_active_bundle()
        assert active is None

    async def test_set_and_get_active_bundle(self, test_db):
        """Test setting and getting active bundle."""
        manager = ConfigManager(test_db)

        await manager.add_bundle(name="active-test", source="test-source")
        await manager.set_active_bundle("active-test")

        active = await manager.get_active_bundle()
        assert active == "active-test"

    async def test_remove_active_bundle_clears_active(self, test_db):
        """Test that removing active bundle clears the active setting."""
        manager = ConfigManager(test_db)

        await manager.add_bundle(name="will-remove", source="test")
        await manager.set_active_bundle("will-remove")
        await manager.remove_bundle("will-remove")

        active = await manager.get_active_bundle()
        assert active is None


@pytest.mark.asyncio
class TestToolRegistryOperations:
    """Test tool registry management."""

    async def test_list_tools_registry_empty(self, test_db):
        """Test listing tools returns a dict (may have data from other tests)."""
        manager = ConfigManager(test_db)
        tools = await manager.list_tools_registry()
        assert isinstance(tools, dict)  # May not be empty if other tests ran

    async def test_add_tool(self, test_db):
        """Test adding a tool to registry."""
        manager = ConfigManager(test_db)
        await manager.add_tool(
            name="tool-custom",
            source="git+https://github.com/example/tool-custom",
            module="tool-custom",
            description="Custom tool",
            config={"timeout": 30},
        )

        tools = await manager.list_tools_registry()
        assert "tool-custom" in tools
        assert tools["tool-custom"]["source"] == "git+https://github.com/example/tool-custom"
        assert tools["tool-custom"]["module"] == "tool-custom"
        assert tools["tool-custom"]["description"] == "Custom tool"
        assert tools["tool-custom"]["config"] == {"timeout": 30}

    async def test_add_tool_module_defaults_to_name(self, test_db):
        """Test that module defaults to name if not provided."""
        manager = ConfigManager(test_db)
        await manager.add_tool(name="tool-auto", source="test-source")

        tool = await manager.get_tool("tool-auto")
        assert tool is not None
        assert tool["module"] == "tool-auto"

    async def test_get_tool(self, test_db):
        """Test getting a tool from registry."""
        manager = ConfigManager(test_db)
        await manager.add_tool(name="tool-get-test", source="test-source")

        tool = await manager.get_tool("tool-get-test")
        assert tool is not None
        assert tool["source"] == "test-source"

    async def test_get_nonexistent_tool(self, test_db):
        """Test getting tool that doesn't exist."""
        manager = ConfigManager(test_db)
        tool = await manager.get_tool("nonexistent")
        assert tool is None

    async def test_remove_tool(self, test_db):
        """Test removing a tool from registry."""
        manager = ConfigManager(test_db)
        await manager.add_tool(name="tool-remove", source="test")

        success = await manager.remove_tool("tool-remove")
        assert success is True

        tool = await manager.get_tool("tool-remove")
        assert tool is None

    async def test_remove_nonexistent_tool(self, test_db):
        """Test removing tool that doesn't exist."""
        manager = ConfigManager(test_db)
        success = await manager.remove_tool("nonexistent")
        assert success is False


@pytest.mark.asyncio
class TestProviderRegistryOperations:
    """Test provider registry management."""

    async def test_list_providers_registry_empty(self, test_db):
        """Test listing providers returns a dict (may have data from other tests)."""
        manager = ConfigManager(test_db)
        providers = await manager.list_providers_registry()
        assert isinstance(providers, dict)  # May not be empty if other tests ran

    async def test_add_provider_registry(self, test_db):
        """Test adding a provider to registry."""
        manager = ConfigManager(test_db)
        await manager.add_provider_registry(
            name="anthropic-prod",
            module="provider-anthropic",
            source="git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
            description="Production Anthropic provider",
            config={"default_model": "claude-sonnet-4-5", "priority": 1},
        )

        providers = await manager.list_providers_registry()
        assert "anthropic-prod" in providers
        assert providers["anthropic-prod"]["module"] == "provider-anthropic"
        assert providers["anthropic-prod"]["description"] == "Production Anthropic provider"
        assert providers["anthropic-prod"]["config"]["default_model"] == "claude-sonnet-4-5"

    async def test_get_provider_registry(self, test_db):
        """Test getting a provider from registry."""
        manager = ConfigManager(test_db)
        await manager.add_provider_registry(
            name="test-provider",
            module="provider-test",
        )

        provider = await manager.get_provider_registry("test-provider")
        assert provider is not None
        assert provider["module"] == "provider-test"

    async def test_get_nonexistent_provider(self, test_db):
        """Test getting provider that doesn't exist."""
        manager = ConfigManager(test_db)
        provider = await manager.get_provider_registry("nonexistent")
        assert provider is None

    async def test_remove_provider_registry(self, test_db):
        """Test removing a provider from registry."""
        manager = ConfigManager(test_db)
        await manager.add_provider_registry(name="remove-test", module="provider-test")

        success = await manager.remove_provider_registry("remove-test")
        assert success is True

        provider = await manager.get_provider_registry("remove-test")
        assert provider is None

    async def test_remove_nonexistent_provider(self, test_db):
        """Test removing provider that doesn't exist."""
        manager = ConfigManager(test_db)
        success = await manager.remove_provider_registry("nonexistent")
        assert success is False


@pytest.mark.asyncio
class TestCacheInvalidation:
    """Test bundle cache invalidation."""

    async def test_invalidate_config_cache_called_on_yaml_update(self, test_db):
        """Test that updating config YAML triggers cache invalidation."""
        from unittest.mock import Mock

        manager = ConfigManager(test_db)

        # Create a mock session manager
        mock_session_manager = Mock()
        mock_session_manager.invalidate_config_cache = Mock()
        manager.set_session_manager(mock_session_manager)

        # Create config
        config = await manager.create_config(
            name="cache-test",
            yaml_content="bundle:\n  name: test\n",
        )

        # Update YAML content
        await manager.update_config(
            config_id=config.config_id,
            yaml_content="bundle:\n  name: test\n  version: 2.0.0\n",
        )

        # Verify cache invalidation was called
        mock_session_manager.invalidate_config_cache.assert_called_once_with(config.config_id)

    async def test_invalidate_cache_not_called_on_metadata_update(self, test_db):
        """Test that updating only metadata doesn't invalidate cache."""
        from unittest.mock import Mock

        manager = ConfigManager(test_db)

        # Create a mock session manager
        mock_session_manager = Mock()
        mock_session_manager.invalidate_config_cache = Mock()
        manager.set_session_manager(mock_session_manager)

        # Create config
        config = await manager.create_config(
            name="metadata-test",
            yaml_content="bundle:\n  name: test\n",
        )

        # Update only name and description (not YAML)
        await manager.update_config(
            config_id=config.config_id,
            name="updated-name",
            description="Updated description",
        )

        # Cache invalidation should NOT be called
        mock_session_manager.invalidate_config_cache.assert_not_called()
