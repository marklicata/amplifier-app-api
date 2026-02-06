"""Comprehensive tests for /configs CRUD API endpoints.

Tests all config operations including:
- Basic CRUD (Create, Read, Update, Delete)
- Helper endpoints for adding tools, providers, bundles to configs
- Validation and error handling
"""

import pytest
from httpx import ASGITransport, AsyncClient

from amplifier_app_api.main import app


# Sample YAML configs for testing
MINIMAL_CONFIG_YAML = """
bundle:
  name: minimal-test-config
  version: 1.0.0
"""

COMPLETE_CONFIG_YAML = """
bundle:
  name: complete-test-config
  version: 1.0.0
  description: A complete test configuration

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main

providers:
  - module: provider-anthropic
    source: git+https://github.com/microsoft/amplifier-module-provider-anthropic@main
    config:
      default_model: claude-sonnet-4-5-20250929
      priority: 1

tools:
  - module: tool-filesystem
  - module: tool-bash

instructions:
  You are a helpful AI assistant for testing purposes.
"""


@pytest.mark.asyncio
class TestConfigCRUD:
    """Test basic CRUD operations for configs."""

    async def test_create_config_minimal(self):
        """Test creating a config with minimal required fields."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/configs",
                json={
                    "name": "test-minimal",
                    "yaml_content": MINIMAL_CONFIG_YAML,
                },
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "test-minimal"
            assert data["config_id"] is not None
            assert "bundle:" in data["yaml_content"]
            assert data["message"] == "Config created successfully"

    async def test_create_config_with_description_and_tags(self):
        """Test creating a config with description and tags."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/configs",
                json={
                    "name": "test-with-metadata",
                    "description": "Test configuration with metadata",
                    "yaml_content": MINIMAL_CONFIG_YAML,
                    "tags": {"env": "test", "team": "platform"},
                },
            )
            assert response.status_code == 201
            data = response.json()
            assert data["description"] == "Test configuration with metadata"
            assert data["tags"]["env"] == "test"
            assert data["tags"]["team"] == "platform"

    async def test_create_config_missing_bundle_name(self):
        """Test that config validation fails without bundle.name."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/configs",
                json={
                    "name": "invalid-config",
                    "yaml_content": "providers:\n  - module: test\n",
                },
            )
            assert response.status_code == 400
            assert "bundle" in response.json()["detail"].lower()

    async def test_create_config_invalid_yaml(self):
        """Test that invalid YAML syntax is rejected."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/configs",
                json={
                    "name": "bad-yaml",
                    "yaml_content": "bundle:\n  name: test\n    invalid: indentation",
                },
            )
            assert response.status_code == 400
            assert "yaml" in response.json()["detail"].lower()

    async def test_list_configs(self):
        """Test listing all configs."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create a config first
            await client.post(
                "/configs",
                json={"name": "list-test", "yaml_content": MINIMAL_CONFIG_YAML},
            )

            # List configs
            response = await client.get("/configs")
            assert response.status_code == 200
            data = response.json()
            assert "configs" in data
            assert "total" in data
            assert isinstance(data["configs"], list)
            assert data["total"] >= 1

    async def test_list_configs_pagination(self):
        """Test config list pagination."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/configs?limit=10&offset=0")
            assert response.status_code == 200
            data = response.json()
            assert len(data["configs"]) <= 10

    async def test_get_config_by_id(self):
        """Test getting a specific config by ID."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create a config
            create_response = await client.post(
                "/configs",
                json={"name": "get-test", "yaml_content": MINIMAL_CONFIG_YAML},
            )
            config_id = create_response.json()["config_id"]

            # Get the config
            response = await client.get(f"/configs/{config_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["config_id"] == config_id
            assert data["name"] == "get-test"

    async def test_get_config_not_found(self):
        """Test getting a non-existent config."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/configs/nonexistent-id")
            assert response.status_code == 404

    async def test_update_config(self):
        """Test updating a config."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create a config
            create_response = await client.post(
                "/configs",
                json={"name": "update-test", "yaml_content": MINIMAL_CONFIG_YAML},
            )
            config_id = create_response.json()["config_id"]

            # Update the config
            new_yaml = """
bundle:
  name: updated-config
  version: 2.0.0
"""
            response = await client.put(
                f"/configs/{config_id}",
                json={
                    "name": "updated-name",
                    "description": "Updated description",
                    "yaml_content": new_yaml,
                    "tags": {"env": "production"},
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "updated-name"
            assert data["description"] == "Updated description"
            assert "updated-config" in data["yaml_content"]
            assert data["tags"]["env"] == "production"

    async def test_update_config_partial(self):
        """Test partial update of config (only some fields)."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create a config
            create_response = await client.post(
                "/configs",
                json={
                    "name": "partial-update-test",
                    "description": "Original description",
                    "yaml_content": MINIMAL_CONFIG_YAML,
                },
            )
            config_id = create_response.json()["config_id"]

            # Update only the description
            response = await client.put(
                f"/configs/{config_id}",
                json={"description": "New description"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "partial-update-test"  # Unchanged
            assert data["description"] == "New description"  # Changed

    async def test_delete_config(self):
        """Test deleting a config."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create a config
            create_response = await client.post(
                "/configs",
                json={"name": "delete-test", "yaml_content": MINIMAL_CONFIG_YAML},
            )
            config_id = create_response.json()["config_id"]

            # Delete the config
            response = await client.delete(f"/configs/{config_id}")
            assert response.status_code == 200
            assert "deleted successfully" in response.json()["message"]

            # Verify it's gone
            get_response = await client.get(f"/configs/{config_id}")
            assert get_response.status_code == 404

    async def test_delete_config_not_found(self):
        """Test deleting a non-existent config."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/configs/nonexistent-id")
            assert response.status_code == 404


@pytest.mark.asyncio
class TestConfigValidation:
    """Test config YAML validation."""

    async def test_yaml_must_be_dict(self):
        """Test that YAML content must be a dictionary."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/configs",
                json={
                    "name": "scalar-yaml",
                    "yaml_content": "just a string",
                },
            )
            assert response.status_code == 400
            assert "dictionary" in response.json()["detail"].lower()

    async def test_bundle_section_required(self):
        """Test that bundle section is required."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/configs",
                json={
                    "name": "no-bundle",
                    "yaml_content": "tools:\n  - module: test\n",
                },
            )
            assert response.status_code == 400
            assert "bundle" in response.json()["detail"].lower()

    async def test_bundle_name_required(self):
        """Test that bundle.name is required."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/configs",
                json={
                    "name": "no-bundle-name",
                    "yaml_content": "bundle:\n  version: 1.0.0\n",
                },
            )
            assert response.status_code == 400
            assert "name" in response.json()["detail"].lower()

    async def test_session_section_optional(self):
        """Test that session section is optional (can come from includes)."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/configs",
                json={
                    "name": "no-session",
                    "yaml_content": """
bundle:
  name: test-config
includes:
  - bundle: foundation
""",
                },
            )
            # Should succeed - session can come from includes
            assert response.status_code == 201


@pytest.mark.asyncio
class TestConfigEdgeCases:
    """Test edge cases and error scenarios."""

    async def test_create_config_empty_name(self):
        """Test creating config with empty name."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/configs",
                json={"name": "", "yaml_content": MINIMAL_CONFIG_YAML},
            )
            assert response.status_code == 422

    async def test_create_config_missing_yaml(self):
        """Test creating config without yaml_content."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/configs",
                json={"name": "missing-yaml"},
            )
            assert response.status_code == 422

    async def test_update_config_invalid_yaml(self):
        """Test updating config with invalid YAML."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create a config
            create_response = await client.post(
                "/configs",
                json={"name": "update-invalid", "yaml_content": MINIMAL_CONFIG_YAML},
            )
            config_id = create_response.json()["config_id"]

            # Try to update with invalid YAML
            response = await client.put(
                f"/configs/{config_id}",
                json={"yaml_content": "invalid: yaml: syntax:"},
            )
            assert response.status_code == 400

    async def test_very_large_yaml(self):
        """Test config with large YAML content."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create a large YAML with many tools
            large_yaml = "bundle:\n  name: large-config\n\ntools:\n"
            for i in range(100):
                large_yaml += f"  - module: tool-{i}\n"

            response = await client.post(
                "/configs",
                json={"name": "large-config", "yaml_content": large_yaml},
            )
            assert response.status_code == 201

    async def test_unicode_in_config(self):
        """Test config with unicode characters."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            unicode_yaml = """
bundle:
  name: unicode-config
  description: "Configuration with emoji 🚀 and unicode: 你好"
"""
            response = await client.post(
                "/configs",
                json={"name": "unicode-test", "yaml_content": unicode_yaml},
            )
            assert response.status_code == 201
            data = response.json()
            assert "🚀" in data["yaml_content"]
            assert "你好" in data["yaml_content"]
