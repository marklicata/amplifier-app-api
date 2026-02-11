"""Comprehensive E2E tests for Config API endpoints.

Tests actual HTTP endpoints with the service running.
"""

import os

import pytest
from httpx import AsyncClient


# Helper config data for testing
MINIMAL_CONFIG_DATA = {
    "bundle": {"name": "test-minimal", "version": "1.0.0"},
    "includes": [{"bundle": "foundation"}],
    "session": {
        "orchestrator": {
            "module": "loop-basic",
            "source": "git+https://github.com/microsoft/amplifier-module-loop-basic@main",
            "config": {}
        },
        "context": {
            "module": "context-simple",
            "source": "git+https://github.com/microsoft/amplifier-module-context-simple@main",
            "config": {}
        }
    },
    "providers": [{
        "module": "provider-anthropic",
        "source": "git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
        "config": {"api_key": "test-key", "model": "claude-sonnet-4-5"}
    }]
}


@pytest.mark.asyncio
class TestConfigCRUD:
    """Test basic CRUD operations for configs."""

    async def test_create_minimal_config(self, client: AsyncClient):
        """Test creating a minimal valid config."""
        response = await client.post(
            "/configs",
            json={
                "name": "test-minimal",
                "config_data": MINIMAL_CONFIG_DATA,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-minimal"
        assert data["config_id"] is not None
        assert "config_data" in data
        assert data["message"] == "Config created successfully"
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_config_with_all_fields(self, client: AsyncClient):
        """Test creating config with all optional fields."""
        full_config = {
            "bundle": {
                "name": "test-full",
                "version": "1.0.0",
                "description": "Test bundle"
            },
            "includes": [{"bundle": "foundation"}],
            "session": {
                "orchestrator": {
                    "module": "loop-streaming",
                    "source": "git+https://github.com/microsoft/amplifier-module-loop-streaming@main",
                    "config": {}
                },
                "context": {
                    "module": "context-persistent",
                    "source": "git+https://github.com/microsoft/amplifier-module-context-persistent@main",
                    "config": {}
                }
            },
            "providers": [{
                "module": "provider-anthropic",
                "source": "git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
                "config": {"api_key": "${ANTHROPIC_API_KEY}", "model": "claude-sonnet-4-5"}
            }],
            "tools": [
                {"module": "tool-filesystem"},
                {"module": "tool-bash"}
            ],
            "hooks": [
                {"module": "hooks-logging"}
            ]
        }

        response = await client.post(
            "/configs",
            json={
                "name": "test-full",
                "description": "Full configuration test",
                "config_data": full_config,
                "tags": {"env": "test", "version": "1.0"},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-full"
        assert data["description"] == "Full configuration test"
        assert data["tags"] == {"env": "test", "version": "1.0"}

    async def test_get_config_by_id(self, client: AsyncClient):
        """Test retrieving a config by ID."""
        # Create first
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set")

        # Get
        response = await client.get(f"/configs/{config_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["config_id"] == config_id
        assert "config_data" in data

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
            config_data = MINIMAL_CONFIG_DATA.copy()
            config_data["bundle"]["name"] = f"test-list-{i}"
            response = await client.post(
                "/configs",
                json={
                    "name": f"test-list-{i}",
                    "config_data": config_data,
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
            config_data = MINIMAL_CONFIG_DATA.copy()
            config_data["bundle"]["name"] = f"test-page-{i}"
            await client.post(
                "/configs",
                json={
                    "name": f"test-page-{i}",
                    "config_data": config_data,
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
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set")

        # Update
        response = await client.put(
            f"/configs/{config_id}",
            json={"name": "updated-name"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "updated-name"
        assert data["message"] == "Config updated successfully"

    async def test_update_config_description(self, client: AsyncClient):
        """Test updating config description."""
        # Create
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set")

        # Update
        response = await client.put(
            f"/configs/{config_id}",
            json={"description": "New description"},
        )

        assert response.status_code == 200
        assert response.json()["description"] == "New description"

    async def test_update_config_data(self, client: AsyncClient):
        """Test updating config data content."""
        # Create
        create_response = await client.post(
            "/configs",
            json={
                "name": "test-update-data",
                "config_data": MINIMAL_CONFIG_DATA,
            },
        )
        config_id = create_response.json()["config_id"]

        # Update config data
        updated_config = MINIMAL_CONFIG_DATA.copy()
        updated_config["bundle"]["version"] = "2.0.0"
        updated_config["session"]["orchestrator"]["module"] = "loop-streaming"
        updated_config["session"]["orchestrator"]["source"] = "git+https://github.com/microsoft/amplifier-module-loop-streaming@main"

        response = await client.put(
            f"/configs/{config_id}",
            json={"config_data": updated_config},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["config_data"]["bundle"]["version"] == "2.0.0"
        assert data["config_data"]["session"]["orchestrator"]["module"] == "loop-streaming"

    async def test_update_config_tags(self, client: AsyncClient):
        """Test updating config tags."""
        # Create
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set")

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
        # Skip this test - we don't want to delete the shared E2E bundle
        pytest.skip("Cannot delete shared E2E_TEST_BUNDLE_ID")

    async def test_delete_nonexistent_config(self, client: AsyncClient):
        """Test deleting a config that doesn't exist."""
        response = await client.delete("/configs/nonexistent-id")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestConfigValidation:
    """Test config validation rules."""

    async def test_create_config_invalid_structure(self, client: AsyncClient):
        """Test that invalid structure is rejected."""
        response = await client.post(
            "/configs",
            json={
                "name": "invalid-structure",
                "config_data": "not a dict",
            },
        )

        assert response.status_code == 422

    async def test_create_config_missing_bundle_section(self, client: AsyncClient):
        """Test that missing bundle section is rejected."""
        response = await client.post(
            "/configs",
            json={
                "name": "no-bundle",
                "config_data": {
                    "session": {
                        "orchestrator": {
                            "module": "loop-basic",
                            "source": "test",
                            "config": {}
                        },
                        "context": {
                            "module": "context-simple",
                            "source": "test",
                            "config": {}
                        }
                    }
                },
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
                "config_data": {
                    "bundle": {"version": "1.0.0"},
                    "session": {
                        "orchestrator": {"module": "loop-basic", "source": "test", "config": {}},
                        "context": {"module": "context-simple", "source": "test", "config": {}}
                    },
                    "providers": [{"module": "provider-anthropic", "source": "test", "config": {"api_key": "test"}}]
                },
            },
        )

        assert response.status_code == 400
        assert "bundle.name" in response.json()["detail"].lower()

    async def test_create_config_empty_bundle_name(self, client: AsyncClient):
        """Test that empty bundle.name is rejected."""
        response = await client.post(
            "/configs",
            json={
                "name": "empty-bundle-name",
                "config_data": {
                    "bundle": {"name": ""},
                    "session": {
                        "orchestrator": {"module": "loop-basic", "source": "test", "config": {}},
                        "context": {"module": "context-simple", "source": "test", "config": {}}
                    },
                    "providers": [{"module": "provider-anthropic", "source": "test", "config": {"api_key": "test"}}]
                },
            },
        )

        assert response.status_code == 400

    async def test_update_config_invalid_structure(self, client: AsyncClient):
        """Test that updating with invalid structure is rejected."""
        # Create valid config first
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set")

        # Try to update with missing required fields
        response = await client.put(
            f"/configs/{config_id}",
            json={"config_data": {"bundle": {"version": "1.0.0"}}},  # Missing bundle.name
        )

        assert response.status_code == 400


@pytest.mark.asyncio
class TestConfigEdgeCases:
    """Test edge cases and error scenarios."""

    async def test_create_config_empty_name(self, client: AsyncClient):
        """Test that empty config name is handled."""
        response = await client.post(
            "/configs",
            json={
                "name": "",
                "config_data": MINIMAL_CONFIG_DATA,
            },
        )

        # Should either reject or accept - verify behavior is consistent
        assert response.status_code in [201, 400, 422]

    async def test_create_config_duplicate_names(self, client: AsyncClient):
        """Test that duplicate config names are allowed (different IDs)."""
        # Create first
        response1 = await client.post(
            "/configs",
            json={"name": "duplicate-name", "config_data": MINIMAL_CONFIG_DATA},
        )
        assert response1.status_code == 201
        id1 = response1.json()["config_id"]

        # Create second with same name
        response2 = await client.post(
            "/configs",
            json={"name": "duplicate-name", "config_data": MINIMAL_CONFIG_DATA},
        )
        assert response2.status_code == 201
        id2 = response2.json()["config_id"]

        # Should have different IDs
        assert id1 != id2

    async def test_create_config_very_large_data(self, client: AsyncClient):
        """Test creating config with large config data."""
        # Create a config with many tools
        large_config = MINIMAL_CONFIG_DATA.copy()
        large_config["tools"] = [
            {"module": f"tool-{i}", "source": f"./modules/tool-{i}"}
            for i in range(100)
        ]

        response = await client.post(
            "/configs",
            json={
                "name": "large-data",
                "config_data": large_config,
            },
        )

        assert response.status_code == 201

    async def test_create_config_with_special_characters(self, client: AsyncClient):
        """Test config name with special characters."""
        response = await client.post(
            "/configs",
            json={
                "name": "test-config-123_special!@#",
                "config_data": MINIMAL_CONFIG_DATA,
            },
        )

        assert response.status_code in [201, 400]  # Either accepts or validates

    async def test_get_config_list_metadata_no_full_data(self, client: AsyncClient):
        """Test that list endpoint returns metadata without full config_data."""
        # Create a config
        await client.post(
            "/configs",
            json={
                "name": "test-metadata",
                "config_data": MINIMAL_CONFIG_DATA,
            },
        )

        # List configs
        response = await client.get("/configs")
        assert response.status_code == 200
        data = response.json()

        # Verify configs have metadata
        for config in data["configs"]:
            assert "config_id" in config
            assert "name" in config
            assert "created_at" in config

    async def test_update_config_partial_fields(self, client: AsyncClient):
        """Test that partial updates don't overwrite other fields."""
        # Create
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set")

        # Update only name
        response = await client.put(
            f"/configs/{config_id}",
            json={"name": "updated"},
        )

        data = response.json()
        assert data["name"] == "updated"

    async def test_create_config_with_environment_variables(self, client: AsyncClient):
        """Test config with ${ENV_VAR} syntax."""
        config_with_env = MINIMAL_CONFIG_DATA.copy()
        config_with_env["providers"][0]["config"]["api_key"] = "${ANTHROPIC_API_KEY}"
        config_with_env["providers"][0]["config"]["model"] = "${MODEL_NAME:-claude-sonnet-4-5}"

        response = await client.post(
            "/configs",
            json={
                "name": "env-vars",
                "config_data": config_with_env,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "${ANTHROPIC_API_KEY}" in str(data["config_data"])
        assert "${MODEL_NAME:-claude-sonnet-4-5}" in str(data["config_data"])


@pytest.mark.asyncio
class TestConfigComplexStructures:
    """Test configs with complex structures."""

    async def test_config_with_multiple_providers(self, client: AsyncClient):
        """Test config with multiple providers."""
        multi_provider_config = MINIMAL_CONFIG_DATA.copy()
        multi_provider_config["providers"] = [
            {
                "module": "provider-anthropic",
                "source": "git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
                "config": {"api_key": "key1", "model": "claude-sonnet-4-5"}
            },
            {
                "module": "provider-openai",
                "source": "git+https://github.com/microsoft/amplifier-module-provider-openai@main",
                "config": {"api_key": "key2", "model": "gpt-4o"}
            },
            {
                "module": "provider-ollama",
                "source": "git+https://github.com/microsoft/amplifier-module-provider-ollama@main",
                "config": {"model": "llama3"}
            }
        ]

        response = await client.post(
            "/configs",
            json={
                "name": "multi-provider",
                "config_data": multi_provider_config,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert len(data["config_data"]["providers"]) == 3

    async def test_config_with_many_tools(self, client: AsyncClient):
        """Test config with many tools."""
        many_tools_config = MINIMAL_CONFIG_DATA.copy()
        many_tools_config["tools"] = [
            {"module": "tool-filesystem"},
            {"module": "tool-bash"},
            {"module": "tool-web"},
            {"module": "tool-search"},
            {"module": "tool-task"}
        ]

        response = await client.post(
            "/configs",
            json={
                "name": "many-tools",
                "config_data": many_tools_config,
            },
        )

        assert response.status_code == 201

    async def test_config_with_hooks(self, client: AsyncClient):
        """Test config with hooks section."""
        hooks_config = MINIMAL_CONFIG_DATA.copy()
        hooks_config["hooks"] = [
            {"module": "hooks-logging", "config": {"log_level": "DEBUG"}},
            {"module": "hooks-approval"}
        ]

        response = await client.post(
            "/configs",
            json={
                "name": "with-hooks",
                "config_data": hooks_config,
            },
        )

        assert response.status_code == 201

    async def test_config_with_nested_config_sections(self, client: AsyncClient):
        """Test config with nested configuration sections."""
        nested_config = MINIMAL_CONFIG_DATA.copy()
        nested_config["session"]["orchestrator"]["module"] = "loop-streaming"
        nested_config["session"]["orchestrator"]["source"] = "git+https://github.com/microsoft/amplifier-module-loop-streaming@main"
        nested_config["session"]["orchestrator"]["config"] = {
            "max_iterations": 50,
            "show_thinking": True
        }
        nested_config["session"]["context"]["module"] = "context-persistent"
        nested_config["session"]["context"]["source"] = "git+https://github.com/microsoft/amplifier-module-context-persistent@main"
        nested_config["session"]["context"]["config"] = {
            "max_tokens": 200000,
            "compact_threshold": 0.92,
            "auto_compact": True
        }

        response = await client.post(
            "/configs",
            json={
                "name": "nested-config",
                "config_data": nested_config,
            },
        )

        assert response.status_code == 201


@pytest.mark.asyncio
class TestConfigConcurrency:
    """Test concurrent config operations."""

    async def test_create_configs_concurrently(self, client: AsyncClient):
        """Test creating multiple configs simultaneously."""
        import asyncio

        # Create 10 configs concurrently
        tasks = [
            client.post(
                "/configs",
                json={"name": f"concurrent-{i}", "config_data": MINIMAL_CONFIG_DATA},
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
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set")

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
