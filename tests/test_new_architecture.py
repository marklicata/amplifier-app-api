"""Test the new Config → Session architecture."""

from datetime import datetime

import pytest

from amplifier_app_api.core.config_manager import ConfigManager
from amplifier_app_api.models import ConfigMetadata


@pytest.mark.asyncio
async def test_config_crud(db):
    """Test basic Config CRUD operations."""
    manager = ConfigManager(db)

    # Create a config
    yaml_content = """
bundle:
  name: test-config
  version: 1.0.0

includes:
  - bundle: foundation

providers:
  - module: provider-anthropic
    config:
      api_key: sk-test-key
      model: claude-sonnet-4-5

session:
  orchestrator: loop-basic
  context: context-simple

tools:
  - module: tool-filesystem
    source: ./modules/tool-filesystem
"""

    config = await manager.create_config(
        name="test-config",
        yaml_content=yaml_content,
        description="Test configuration",
        tags={"env": "test", "version": "1.0"},
    )

    assert config.config_id is not None
    assert config.name == "test-config"
    assert config.description == "Test configuration"
    assert config.yaml_content == yaml_content
    assert config.tags == {"env": "test", "version": "1.0"}
    assert isinstance(config.created_at, datetime)
    assert isinstance(config.updated_at, datetime)

    # Get the config
    retrieved = await manager.get_config(config.config_id)
    assert retrieved is not None
    assert retrieved.config_id == config.config_id
    assert retrieved.name == config.name
    assert retrieved.yaml_content == yaml_content

    # Update the config
    updated_yaml = yaml_content + "\n# Updated"
    updated = await manager.update_config(
        config.config_id,
        name="updated-config",
        yaml_content=updated_yaml,
        description="Updated description",
    )

    assert updated is not None
    assert updated.name == "updated-config"
    assert updated.description == "Updated description"
    assert updated.yaml_content == updated_yaml
    assert updated.updated_at > config.updated_at

    # List configs
    configs, total = await manager.list_configs(limit=10, offset=0)
    assert total >= 1
    assert any(c.config_id == config.config_id for c in configs)

    # Delete the config
    deleted = await manager.delete_config(config.config_id)
    assert deleted is True

    # Verify deletion
    retrieved_after_delete = await manager.get_config(config.config_id)
    assert retrieved_after_delete is None


@pytest.mark.asyncio
async def test_config_yaml_validation(db):
    """Test that invalid YAML is rejected."""
    manager = ConfigManager(db)

    # Invalid YAML - missing colon
    invalid_yaml = """
bundle
  name test-config
"""

    with pytest.raises(ValueError, match="Invalid YAML"):
        await manager.create_config(
            name="invalid-config",
            yaml_content=invalid_yaml,
        )


@pytest.mark.asyncio
async def test_config_helper_methods(db):
    """Test programmatic config manipulation helpers."""
    manager = ConfigManager(db)

    # Create a minimal config
    yaml_content = """
bundle:
  name: test-config
  version: 1.0.0
"""

    config = await manager.create_config(
        name="test-config",
        yaml_content=yaml_content,
    )

    # Add a tool
    updated = await manager.add_tool_to_config(
        config.config_id,
        module="tool-web",
        source="./modules/tool-web",
        config={"timeout": 30},
    )

    assert updated is not None
    parsed = manager.parse_yaml(updated.yaml_content)
    assert "tools" in parsed
    assert len(parsed["tools"]) == 1
    assert parsed["tools"][0]["module"] == "tool-web"
    assert parsed["tools"][0]["source"] == "./modules/tool-web"
    assert parsed["tools"][0]["config"]["timeout"] == 30

    # Add a provider
    updated = await manager.add_provider_to_config(
        config.config_id,
        module="provider-anthropic",
        source="git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
        config={"api_key": "test-key", "model": "claude-sonnet-4-5"},
    )

    assert updated is not None
    parsed = manager.parse_yaml(updated.yaml_content)
    assert "providers" in parsed
    assert len(parsed["providers"]) == 1
    assert parsed["providers"][0]["module"] == "provider-anthropic"
    assert parsed["providers"][0]["config"]["api_key"] == "test-key"

    # Merge a bundle
    updated = await manager.merge_bundle_into_config(
        config.config_id,
        bundle_uri="foundation",
    )

    assert updated is not None
    parsed = manager.parse_yaml(updated.yaml_content)
    assert "includes" in parsed
    assert len(parsed["includes"]) == 1
    assert parsed["includes"][0]["bundle"] == "foundation"

    # Cleanup
    await manager.delete_config(config.config_id)


@pytest.mark.asyncio
async def test_config_yaml_parsing(db):
    """Test YAML parsing and dumping utilities."""
    manager = ConfigManager(db)

    # Test parsing
    yaml_str = """
bundle:
  name: test
  version: 1.0.0
providers:
  - module: provider-anthropic
    config:
      model: claude-sonnet-4-5
"""

    parsed = manager.parse_yaml(yaml_str)
    assert parsed["bundle"]["name"] == "test"
    assert parsed["bundle"]["version"] == "1.0.0"
    assert parsed["providers"][0]["module"] == "provider-anthropic"

    # Test dumping
    data = {
        "bundle": {"name": "test", "version": "1.0.0"},
        "providers": [{"module": "provider-anthropic"}],
    }

    dumped = manager.dump_yaml(data)
    assert "bundle:" in dumped
    assert "name: test" in dumped
    assert "providers:" in dumped


@pytest.mark.asyncio
async def test_config_list_pagination(db):
    """Test config listing with pagination."""
    manager = ConfigManager(db)

    # Create multiple configs
    config_ids = []
    for i in range(5):
        config = await manager.create_config(
            name=f"config-{i}",
            yaml_content=f"bundle:\n  name: config-{i}",
        )
        config_ids.append(config.config_id)

    # Test pagination
    configs, total = await manager.list_configs(limit=2, offset=0)
    assert len(configs) == 2
    assert total >= 5

    configs, total = await manager.list_configs(limit=2, offset=2)
    assert len(configs) == 2

    configs, total = await manager.list_configs(limit=10, offset=0)
    assert len(configs) >= 5

    # Cleanup
    for config_id in config_ids:
        await manager.delete_config(config_id)


@pytest.mark.asyncio
async def test_config_metadata_structure(db):
    """Test that ConfigMetadata has correct structure."""
    manager = ConfigManager(db)

    config = await manager.create_config(
        name="test-metadata",
        yaml_content="bundle:\n  name: test",
        description="Test description",
        tags={"key": "value"},
    )

    configs, _ = await manager.list_configs(limit=10)
    metadata = next(c for c in configs if c.config_id == config.config_id)

    assert isinstance(metadata, ConfigMetadata)
    assert metadata.config_id == config.config_id
    assert metadata.name == config.name
    assert metadata.description == config.description
    assert metadata.tags == {"key": "value"}
    assert isinstance(metadata.created_at, datetime)
    assert isinstance(metadata.updated_at, datetime)

    # Cleanup
    await manager.delete_config(config.config_id)


@pytest.mark.asyncio
async def test_config_update_partial(db):
    """Test partial updates to config."""
    manager = ConfigManager(db)

    config = await manager.create_config(
        name="original",
        yaml_content="bundle:\n  name: test",
        description="Original description",
        tags={"version": "1.0"},
    )

    # Update only name
    updated = await manager.update_config(config.config_id, name="updated-name")
    assert updated is not None
    assert updated.name == "updated-name"
    assert updated.description == "Original description"
    assert updated.yaml_content == "bundle:\n  name: test"

    # Update only description
    updated = await manager.update_config(config.config_id, description="Updated description")
    assert updated is not None
    assert updated.name == "updated-name"
    assert updated.description == "Updated description"

    # Update only tags
    updated = await manager.update_config(config.config_id, tags={"version": "2.0"})
    assert updated is not None
    assert updated.tags == {"version": "2.0"}

    # Cleanup
    await manager.delete_config(config.config_id)


@pytest.mark.asyncio
async def test_config_nonexistent_operations(db):
    """Test operations on non-existent configs."""
    manager = ConfigManager(db)

    fake_id = "nonexistent-config-id"

    # Get non-existent config
    config = await manager.get_config(fake_id)
    assert config is None

    # Update non-existent config
    updated = await manager.update_config(fake_id, name="new-name")
    assert updated is None

    # Delete non-existent config
    deleted = await manager.delete_config(fake_id)
    assert deleted is False

    # Helper methods on non-existent config
    result = await manager.add_tool_to_config(fake_id, module="tool-web", source="./tool-web")
    assert result is None

    result = await manager.add_provider_to_config(fake_id, module="provider-anthropic")
    assert result is None

    result = await manager.merge_bundle_into_config(fake_id, bundle_uri="foundation")
    assert result is None
