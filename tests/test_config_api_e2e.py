"""Comprehensive E2E tests for Config API endpoints.

Tests actual HTTP endpoints with the service running.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestConfigCRUD:
    """Test basic CRUD operations for configs."""

    async def test_create_minimal_config(self, client: AsyncClient):
        """Test creating a minimal valid config."""
        response = await client.post(
            "/configs",
            json={
                "name": "test-minimal",
                "yaml_content": """
bundle:
  name: test-minimal

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: test-key
      model: claude-sonnet-4-5
""",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-minimal"
        assert data["config_id"] is not None
        assert "yaml_content" in data
        assert data["message"] == "Config created successfully"
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_config_with_all_fields(self, client: AsyncClient):
        """Test creating config with all optional fields."""
        response = await client.post(
            "/configs",
            json={
                "name": "test-full",
                "description": "Full configuration test",
                "yaml_content": """
bundle:
  name: test-full
  version: 1.0.0
  description: Test bundle

includes:
  - bundle: foundation

providers:
  - module: provider-anthropic
    config:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-5

session:
  orchestrator: loop-streaming
  context: context-persistent

tools:
  - module: tool-filesystem
  - module: tool-bash

hooks:
  - module: hooks-logging
""",
                "tags": {"env": "test", "version": "1.0"},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-full"
        assert data["description"] == "Full configuration test"
        assert data["tags"] == {"env": "test", "version": "1.0"}

    async def test_create_config_with_markdown_body(self, client: AsyncClient):
        """Test creating config with YAML frontmatter and markdown body."""
        response = await client.post(
            "/configs",
            json={
                "name": "test-markdown",
                "yaml_content": """---
bundle:
  name: test-markdown

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: test-key
---

# Test Instructions

You are a test assistant.

## Guidelines

- Be helpful
- Be concise
""",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "Test Instructions" in data["yaml_content"]
        assert "Guidelines" in data["yaml_content"]

    async def test_get_config_by_id(self, client: AsyncClient):
        """Test retrieving a config by ID."""
        # Create first
        create_response = await client.post(
            "/configs",
            json={
                "name": "test-get",
                "yaml_content": "bundle:\n  name: test-get\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
            },
        )
        config_id = create_response.json()["config_id"]

        # Get
        response = await client.get(f"/configs/{config_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["config_id"] == config_id
        assert data["name"] == "test-get"
        assert "yaml_content" in data

    async def test_get_nonexistent_config(self, client: AsyncClient):
        """Test getting a config that doesn't exist."""
        response = await client.get("/configs/nonexistent-config-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_list_configs_empty(self, client: AsyncClient):
        """Test listing configs when none exist (or cleanup first)."""
        response = await client.get("/configs")
        assert response.status_code == 200
        data = response.json()
        assert "configs" in data
        assert "total" in data
        assert isinstance(data["configs"], list)

    async def test_list_configs_with_data(self, client: AsyncClient):
        """Test listing configs after creating some."""
        # Create multiple configs
        config_ids = []
        for i in range(3):
            response = await client.post(
                "/configs",
                json={
                    "name": f"test-list-{i}",
                    "yaml_content": f"bundle:\n  name: test-{i}\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
                },
            )
            config_ids.append(response.json()["config_id"])

        # List
        response = await client.get("/configs")
        assert response.status_code == 200
        data = response.json()
        assert len(data["configs"]) >= 3
        assert data["total"] >= 3

        # Verify our configs are in the list
        listed_ids = {c["config_id"] for c in data["configs"]}
        for config_id in config_ids:
            assert config_id in listed_ids

    async def test_list_configs_pagination(self, client: AsyncClient):
        """Test config list pagination."""
        # Create 5 configs
        for i in range(5):
            await client.post(
                "/configs",
                json={
                    "name": f"test-page-{i}",
                    "yaml_content": f"bundle:\n  name: test-page-{i}\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
                },
            )

        # Get first page
        response = await client.get("/configs?limit=2&offset=0")
        assert response.status_code == 200
        page1 = response.json()
        assert len(page1["configs"]) == 2

        # Get second page
        response = await client.get("/configs?limit=2&offset=2")
        assert response.status_code == 200
        page2 = response.json()
        assert len(page2["configs"]) == 2

        # Verify different configs
        page1_ids = {c["config_id"] for c in page1["configs"]}
        page2_ids = {c["config_id"] for c in page2["configs"]}
        assert page1_ids.isdisjoint(page2_ids)

    async def test_update_config_name(self, client: AsyncClient):
        """Test updating just the config name."""
        # Create
        create_response = await client.post(
            "/configs",
            json={
                "name": "original-name",
                "yaml_content": "bundle:\n  name: test\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
            },
        )
        config_id = create_response.json()["config_id"]
        original_yaml = create_response.json()["yaml_content"]

        # Update
        response = await client.put(
            f"/configs/{config_id}",
            json={"name": "updated-name"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "updated-name"
        assert data["yaml_content"] == original_yaml  # YAML unchanged
        assert data["message"] == "Config updated successfully"

    async def test_update_config_description(self, client: AsyncClient):
        """Test updating config description."""
        # Create
        create_response = await client.post(
            "/configs",
            json={
                "name": "test-desc",
                "yaml_content": "bundle:\n  name: test\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
            },
        )
        config_id = create_response.json()["config_id"]

        # Update
        response = await client.put(
            f"/configs/{config_id}",
            json={"description": "New description"},
        )

        assert response.status_code == 200
        assert response.json()["description"] == "New description"

    async def test_update_config_yaml(self, client: AsyncClient):
        """Test updating config YAML content."""
        # Create
        create_response = await client.post(
            "/configs",
            json={
                "name": "test-update-yaml",
                "yaml_content": """
bundle:
  name: test
  version: 1.0.0

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: test
""",
            },
        )
        config_id = create_response.json()["config_id"]

        # Update YAML
        response = await client.put(
            f"/configs/{config_id}",
            json={
                "yaml_content": """
bundle:
  name: test
  version: 2.0.0

session:
  orchestrator: loop-streaming
  context: context-persistent

providers:
  - module: provider-anthropic
    config:
      api_key: updated-key
"""
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "version: 2.0.0" in data["yaml_content"]
        assert "loop-streaming" in data["yaml_content"]

    async def test_update_config_tags(self, client: AsyncClient):
        """Test updating config tags."""
        # Create
        create_response = await client.post(
            "/configs",
            json={
                "name": "test-tags",
                "yaml_content": "bundle:\n  name: test\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
                "tags": {"env": "dev"},
            },
        )
        config_id = create_response.json()["config_id"]

        # Update tags
        response = await client.put(
            f"/configs/{config_id}",
            json={"tags": {"env": "staging", "version": "1.0"}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tags"] == {"env": "staging", "version": "1.0"}

    async def test_update_nonexistent_config(self, client: AsyncClient):
        """Test updating a config that doesn't exist."""
        response = await client.put(
            "/configs/nonexistent-id",
            json={"name": "new-name"},
        )
        assert response.status_code == 404

    async def test_delete_config(self, client: AsyncClient):
        """Test deleting a config."""
        # Create
        create_response = await client.post(
            "/configs",
            json={
                "name": "test-delete",
                "yaml_content": "bundle:\n  name: test\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
            },
        )
        config_id = create_response.json()["config_id"]

        # Delete
        response = await client.delete(f"/configs/{config_id}")
        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"].lower()

        # Verify deleted
        get_response = await client.get(f"/configs/{config_id}")
        assert get_response.status_code == 404

    async def test_delete_nonexistent_config(self, client: AsyncClient):
        """Test deleting a config that doesn't exist."""
        response = await client.delete("/configs/nonexistent-id")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestConfigValidation:
    """Test config validation rules."""

    async def test_create_config_invalid_yaml_syntax(self, client: AsyncClient):
        """Test that invalid YAML syntax is rejected."""
        response = await client.post(
            "/configs",
            json={
                "name": "invalid-yaml",
                "yaml_content": "bundle\n  name test",  # Missing colons
            },
        )

        assert response.status_code == 400
        assert "yaml" in response.json()["detail"].lower()

    async def test_create_config_missing_bundle_section(self, client: AsyncClient):
        """Test that missing bundle section is rejected."""
        response = await client.post(
            "/configs",
            json={
                "name": "no-bundle",
                "yaml_content": """
session:
  orchestrator: loop-basic
  context: context-simple
""",
            },
        )

        assert response.status_code == 400
        assert "bundle" in response.json()["detail"].lower()

    async def test_create_config_missing_bundle_name(self, client: AsyncClient):
        """Test that missing bundle.name is rejected."""
        response = await client.post(
            "/configs",
            json={
                "name": "no-bundle-name",
                "yaml_content": """
bundle:
  version: 1.0.0

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: test
""",
            },
        )

        assert response.status_code == 400
        assert "bundle.name" in response.json()["detail"].lower()

    async def test_create_config_missing_session_section(self, client: AsyncClient):
        """Test that missing session section is rejected."""
        response = await client.post(
            "/configs",
            json={
                "name": "no-session",
                "yaml_content": """
bundle:
  name: test
""",
            },
        )

        assert response.status_code == 400
        assert "session" in response.json()["detail"].lower()

    async def test_create_config_missing_orchestrator(self, client: AsyncClient):
        """Test that missing session.orchestrator is rejected."""
        response = await client.post(
            "/configs",
            json={
                "name": "no-orchestrator",
                "yaml_content": """
bundle:
  name: test

session:
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: test
""",
            },
        )

        assert response.status_code == 400
        assert "orchestrator" in response.json()["detail"].lower()

    async def test_create_config_missing_context_manager(self, client: AsyncClient):
        """Test that missing session.context is rejected."""
        response = await client.post(
            "/configs",
            json={
                "name": "no-context",
                "yaml_content": """
bundle:
  name: test

session:
  orchestrator: loop-basic

providers:
  - module: provider-anthropic
    config:
      api_key: test
""",
            },
        )

        assert response.status_code == 400
        assert "context" in response.json()["detail"].lower()

    async def test_create_config_empty_bundle_name(self, client: AsyncClient):
        """Test that empty bundle.name is rejected."""
        response = await client.post(
            "/configs",
            json={
                "name": "empty-bundle-name",
                "yaml_content": """
bundle:
  name: ""

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: test
""",
            },
        )

        assert response.status_code == 400

    async def test_update_config_invalid_yaml(self, client: AsyncClient):
        """Test that updating with invalid YAML is rejected."""
        # Create valid config first
        create_response = await client.post(
            "/configs",
            json={
                "name": "test-update-invalid",
                "yaml_content": "bundle:\n  name: test\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
            },
        )
        config_id = create_response.json()["config_id"]

        # Try to update with invalid YAML
        response = await client.put(
            f"/configs/{config_id}",
            json={"yaml_content": "invalid yaml [[["},
        )

        assert response.status_code == 400
        assert "yaml" in response.json()["detail"].lower()

    async def test_update_config_invalid_structure(self, client: AsyncClient):
        """Test that updating with invalid structure is rejected."""
        # Create valid config first
        create_response = await client.post(
            "/configs",
            json={
                "name": "test-update-structure",
                "yaml_content": "bundle:\n  name: test\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
            },
        )
        config_id = create_response.json()["config_id"]

        # Try to update with missing required fields
        response = await client.put(
            f"/configs/{config_id}",
            json={"yaml_content": "bundle:\n  version: 1.0.0"},  # Missing bundle.name
        )

        assert response.status_code == 400

    async def test_create_config_scalar_yaml(self, client: AsyncClient):
        """Test that scalar YAML (not dict) is rejected."""
        response = await client.post(
            "/configs",
            json={
                "name": "scalar-yaml",
                "yaml_content": "just a string",
            },
        )

        assert response.status_code == 400


@pytest.mark.asyncio
class TestConfigHelpers:
    """Test programmatic config manipulation helpers."""

    async def test_add_tool_to_config(self, client: AsyncClient):
        """Test adding a tool to config via helper endpoint."""
        # Create base config
        create_response = await client.post(
            "/configs",
            json={
                "name": "test-add-tool",
                "yaml_content": """
bundle:
  name: test

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: test
""",
            },
        )
        config_id = create_response.json()["config_id"]

        # Add tool
        response = await client.post(
            f"/configs/{config_id}/tools",
            params={
                "tool_module": "tool-web",
                "tool_source": "./modules/tool-web",
            },
            json={"timeout": 30},
        )

        assert response.status_code == 200
        data = response.json()
        assert "tool-web" in data["yaml_content"]
        assert "tools:" in data["yaml_content"]

    async def test_add_provider_to_config(self, client: AsyncClient):
        """Test adding a provider to config via helper endpoint."""
        # Create base config with one provider
        create_response = await client.post(
            "/configs",
            json={
                "name": "test-add-provider",
                "yaml_content": """
bundle:
  name: test

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: test-key-1
""",
            },
        )
        config_id = create_response.json()["config_id"]

        # Add second provider
        response = await client.post(
            f"/configs/{config_id}/providers",
            params={"provider_module": "provider-openai"},
            json={"api_key": "test-key-2", "model": "gpt-4o"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "provider-openai" in data["yaml_content"]
        assert "provider-anthropic" in data["yaml_content"]  # Original still there

    async def test_merge_bundle_into_config(self, client: AsyncClient):
        """Test merging a bundle into config via helper endpoint."""
        # Create base config
        create_response = await client.post(
            "/configs",
            json={
                "name": "test-merge-bundle",
                "yaml_content": """
bundle:
  name: test

includes:
  - bundle: foundation

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: test
""",
            },
        )
        config_id = create_response.json()["config_id"]

        # Merge another bundle
        response = await client.post(
            f"/configs/{config_id}/bundles",
            params={"bundle_uri": "recipes"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "foundation" in data["yaml_content"]
        assert "recipes" in data["yaml_content"]

    async def test_add_tool_to_nonexistent_config(self, client: AsyncClient):
        """Test that adding tool to nonexistent config fails."""
        response = await client.post(
            "/configs/nonexistent/tools",
            params={"tool_module": "tool-web", "tool_source": "./tool-web"},
        )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestConfigEdgeCases:
    """Test edge cases and error scenarios."""

    async def test_create_config_empty_name(self, client: AsyncClient):
        """Test that empty config name is handled."""
        response = await client.post(
            "/configs",
            json={
                "name": "",
                "yaml_content": "bundle:\n  name: test\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
            },
        )

        # Should either reject or accept - verify behavior is consistent
        assert response.status_code in [201, 400]

    async def test_create_config_duplicate_names(self, client: AsyncClient):
        """Test that duplicate config names are allowed (different IDs)."""
        yaml = "bundle:\n  name: test\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test"

        # Create first
        response1 = await client.post(
            "/configs",
            json={"name": "duplicate-name", "yaml_content": yaml},
        )
        assert response1.status_code == 201
        id1 = response1.json()["config_id"]

        # Create second with same name
        response2 = await client.post(
            "/configs",
            json={"name": "duplicate-name", "yaml_content": yaml},
        )
        assert response2.status_code == 201
        id2 = response2.json()["config_id"]

        # Should have different IDs
        assert id1 != id2

    async def test_create_config_very_large_yaml(self, client: AsyncClient):
        """Test creating config with large YAML content."""
        # Create a config with many tools
        tools_yaml = "\n".join(
            [f"  - module: tool-{i}\n    source: ./modules/tool-{i}" for i in range(100)]
        )

        response = await client.post(
            "/configs",
            json={
                "name": "large-yaml",
                "yaml_content": f"""
bundle:
  name: large-test

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: test

tools:
{tools_yaml}
""",
            },
        )

        assert response.status_code == 201

    async def test_create_config_with_special_characters(self, client: AsyncClient):
        """Test config name with special characters."""
        response = await client.post(
            "/configs",
            json={
                "name": "test-config-123_special!@#",
                "yaml_content": "bundle:\n  name: test\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
            },
        )

        assert response.status_code in [201, 400]  # Either accepts or validates

    async def test_get_config_list_metadata_no_yaml(self, client: AsyncClient):
        """Test that list endpoint returns metadata without yaml_content."""
        # Create a config
        await client.post(
            "/configs",
            json={
                "name": "test-metadata",
                "yaml_content": "bundle:\n  name: test\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
            },
        )

        # List configs
        response = await client.get("/configs")
        assert response.status_code == 200
        data = response.json()

        # Verify configs have metadata but NOT yaml_content
        for config in data["configs"]:
            assert "config_id" in config
            assert "name" in config
            assert "created_at" in config
            assert "yaml_content" not in config  # Should NOT be in list

    async def test_update_config_partial_fields(self, client: AsyncClient):
        """Test that partial updates don't overwrite other fields."""
        # Create
        create_response = await client.post(
            "/configs",
            json={
                "name": "original",
                "description": "original desc",
                "yaml_content": "bundle:\n  name: test\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
                "tags": {"env": "test"},
            },
        )
        config_id = create_response.json()["config_id"]

        # Update only name
        response = await client.put(
            f"/configs/{config_id}",
            json={"name": "updated"},
        )

        data = response.json()
        assert data["name"] == "updated"
        assert data["description"] == "original desc"  # Unchanged
        assert data["tags"] == {"env": "test"}  # Unchanged

    async def test_create_config_with_environment_variables(self, client: AsyncClient):
        """Test config with ${ENV_VAR} syntax."""
        response = await client.post(
            "/configs",
            json={
                "name": "env-vars",
                "yaml_content": """
bundle:
  name: env-test

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: ${ANTHROPIC_API_KEY}
      model: ${MODEL_NAME:-claude-sonnet-4-5}
""",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "${ANTHROPIC_API_KEY}" in data["yaml_content"]
        assert "${MODEL_NAME:-claude-sonnet-4-5}" in data["yaml_content"]


@pytest.mark.asyncio
class TestConfigComplexStructures:
    """Test configs with complex YAML structures."""

    async def test_config_with_multiple_providers(self, client: AsyncClient):
        """Test config with multiple providers."""
        response = await client.post(
            "/configs",
            json={
                "name": "multi-provider",
                "yaml_content": """
bundle:
  name: multi-provider

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: key1
      model: claude-sonnet-4-5
  - module: provider-openai
    config:
      api_key: key2
      model: gpt-4o
  - module: provider-ollama
    config:
      model: llama3
""",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "provider-anthropic" in data["yaml_content"]
        assert "provider-openai" in data["yaml_content"]
        assert "provider-ollama" in data["yaml_content"]

    async def test_config_with_many_tools(self, client: AsyncClient):
        """Test config with many tools."""
        response = await client.post(
            "/configs",
            json={
                "name": "many-tools",
                "yaml_content": """
bundle:
  name: many-tools

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: test

tools:
  - module: tool-filesystem
  - module: tool-bash
  - module: tool-web
  - module: tool-search
  - module: tool-task
""",
            },
        )

        assert response.status_code == 201

    async def test_config_with_hooks(self, client: AsyncClient):
        """Test config with hooks section."""
        response = await client.post(
            "/configs",
            json={
                "name": "with-hooks",
                "yaml_content": """
bundle:
  name: hooks-test

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: test

hooks:
  - module: hooks-logging
    config:
      log_level: DEBUG
  - module: hooks-approval
""",
            },
        )

        assert response.status_code == 201

    async def test_config_with_spawn_policy(self, client: AsyncClient):
        """Test config with spawn configuration."""
        response = await client.post(
            "/configs",
            json={
                "name": "with-spawn",
                "yaml_content": """
bundle:
  name: spawn-test

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: test

spawn:
  exclude_tools:
    - tool-task
    - tool-bash
""",
            },
        )

        assert response.status_code == 201

    async def test_config_with_nested_config_sections(self, client: AsyncClient):
        """Test config with nested configuration sections."""
        response = await client.post(
            "/configs",
            json={
                "name": "nested-config",
                "yaml_content": """
bundle:
  name: nested-test

session:
  orchestrator: loop-streaming
  context: context-persistent
  injection_budget_per_turn: 500

orchestrator:
  config:
    max_iterations: 50
    show_thinking: true

context:
  config:
    max_tokens: 200000
    compact_threshold: 0.92
    auto_compact: true

providers:
  - module: provider-anthropic
    config:
      api_key: test
""",
            },
        )

        assert response.status_code == 201


@pytest.mark.asyncio
class TestConfigConcurrency:
    """Test concurrent config operations."""

    async def test_create_configs_concurrently(self, client: AsyncClient):
        """Test creating multiple configs simultaneously."""
        import asyncio

        yaml = "bundle:\n  name: test\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test"

        # Create 10 configs concurrently
        tasks = [
            client.post(
                "/configs",
                json={"name": f"concurrent-{i}", "yaml_content": yaml},
            )
            for i in range(10)
        ]

        responses = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r.status_code == 201 for r in responses)

        # All should have unique IDs
        ids = [r.json()["config_id"] for r in responses]
        assert len(ids) == len(set(ids))  # No duplicates

    async def test_update_config_concurrently(self, client: AsyncClient):
        """Test updating same config from multiple requests."""
        # Create a config
        create_response = await client.post(
            "/configs",
            json={
                "name": "concurrent-update",
                "yaml_content": "bundle:\n  name: test\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
            },
        )
        config_id = create_response.json()["config_id"]

        # Update concurrently
        import asyncio

        tasks = [
            client.put(
                f"/configs/{config_id}",
                json={"description": f"Update {i}"},
            )
            for i in range(5)
        ]

        responses = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

        # Final state should be consistent
        final_response = await client.get(f"/configs/{config_id}")
        assert final_response.status_code == 200


@pytest.mark.asyncio
class TestConfigCleanup:
    """Test cleanup and deletion scenarios."""

    async def test_delete_all_created_configs(self, client: AsyncClient):
        """Clean up all test configs."""
        # List all configs
        response = await client.get("/configs?limit=1000")
        configs = response.json()["configs"]

        # Delete all test configs
        for config in configs:
            if config["name"].startswith("test-") or config["name"].startswith("concurrent-"):
                await client.delete(f"/configs/{config['config_id']}")

        # Verify cleanup
        final_response = await client.get("/configs")
        final_configs = final_response.json()["configs"]
        test_configs = [c for c in final_configs if c["name"].startswith("test-")]
        assert len(test_configs) == 0
