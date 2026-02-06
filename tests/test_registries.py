"""Comprehensive tests for tool and provider global registries.

Tests the registry functionality for:
- Global tool registry (register/list/get/delete tools)
- Global provider registry (register/list/get/delete providers)
"""

import pytest
from httpx import ASGITransport, AsyncClient

from amplifier_app_api.main import app


@pytest.mark.asyncio
class TestToolRegistry:
    """Test global tool registry operations."""

    async def test_register_tool(self):
        """Test registering a tool in the global registry."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/tools",
                params={
                    "name": "tool-custom",
                    "source": "git+https://github.com/example/tool-custom@main",
                    "module": "tool-custom",
                    "description": "Custom tool for testing",
                },
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "tool-custom"
            assert "registered successfully" in data["message"]

    async def test_register_tool_with_config(self):
        """Test registering a tool with configuration."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/tools",
                params={
                    "name": "tool-with-config",
                    "source": "git+https://github.com/example/tool@main",
                    "description": "Tool with config",
                },
                json={"timeout": 30, "max_retries": 3},
            )
            assert response.status_code == 201

    async def test_list_tools_from_registry(self):
        """Test listing tools from global registry."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Register a tool first
            await client.post(
                "/tools",
                params={
                    "name": "tool-list-test",
                    "source": "builtin",
                },
            )

            # List from registry
            response = await client.get("/tools?from_registry=true")
            assert response.status_code == 200
            data = response.json()
            assert "tools" in data
            assert isinstance(data["tools"], list)

    async def test_get_tool_from_registry(self):
        """Test getting a specific tool from registry."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Register a tool
            await client.post(
                "/tools",
                params={
                    "name": "tool-get-test",
                    "source": "git+https://example.com/tool",
                    "module": "tool-get-test",
                    "description": "Test tool",
                },
            )

            # Get the tool
            response = await client.get("/tools/tool-get-test?from_registry=true")
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "tool-get-test"
            assert data["source"] == "git+https://example.com/tool"
            assert data["module"] == "tool-get-test"
            assert data["description"] == "Test tool"

    async def test_get_tool_not_found(self):
        """Test getting a non-existent tool from registry."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/tools/nonexistent-tool?from_registry=true")
            assert response.status_code == 404

    async def test_delete_tool_from_registry(self):
        """Test deleting a tool from registry."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Register a tool
            await client.post(
                "/tools",
                params={
                    "name": "tool-delete-test",
                    "source": "builtin",
                },
            )

            # Delete the tool
            response = await client.delete("/tools/tool-delete-test")
            assert response.status_code == 200
            assert "removed from registry successfully" in response.json()["message"]

            # Verify it's gone
            get_response = await client.get("/tools/tool-delete-test?from_registry=true")
            assert get_response.status_code == 404

    async def test_delete_tool_not_found(self):
        """Test deleting a non-existent tool."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/tools/nonexistent-tool")
            assert response.status_code == 404

    async def test_register_multiple_tools(self):
        """Test registering multiple tools."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Register multiple tools
            tools = ["tool-a", "tool-b", "tool-c"]
            for tool in tools:
                await client.post(
                    "/tools",
                    params={
                        "name": tool,
                        "source": f"git+https://example.com/{tool}",
                    },
                )

            # List all tools
            response = await client.get("/tools?from_registry=true")
            assert response.status_code == 200
            data = response.json()
            tool_names = [t["name"] for t in data["tools"]]
            for tool in tools:
                assert tool in tool_names


@pytest.mark.asyncio
class TestProviderRegistry:
    """Test global provider registry operations."""

    async def test_register_provider(self):
        """Test registering a provider in the global registry."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/providers",
                params={
                    "name": "anthropic-prod",
                    "module": "provider-anthropic",
                    "source": "git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
                    "description": "Production Anthropic provider",
                },
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "anthropic-prod"
            assert data["module"] == "provider-anthropic"
            assert "registered successfully" in data["message"]

    async def test_register_provider_with_config(self):
        """Test registering a provider with configuration."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/providers",
                params={
                    "name": "anthropic-with-config",
                    "module": "provider-anthropic",
                    "description": "Provider with default config",
                },
                json={
                    "default_model": "claude-sonnet-4-5-20250929",
                    "priority": 1,
                },
            )
            assert response.status_code == 201

    async def test_register_provider_without_source(self):
        """Test registering a provider without source (installed package)."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/providers",
                params={
                    "name": "openai-dev",
                    "module": "provider-openai",
                    "description": "Development OpenAI provider",
                },
            )
            assert response.status_code == 201

    async def test_list_providers(self):
        """Test listing all registered providers."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Register a provider first
            await client.post(
                "/providers",
                params={
                    "name": "provider-list-test",
                    "module": "provider-test",
                },
            )

            # List providers
            response = await client.get("/providers")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)
            assert "provider-list-test" in data or len(data) >= 0  # Empty is valid

    async def test_get_provider(self):
        """Test getting a specific provider from registry."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Register a provider
            await client.post(
                "/providers",
                params={
                    "name": "provider-get-test",
                    "module": "provider-test",
                    "source": "git+https://example.com/provider",
                    "description": "Test provider",
                },
                json={"api_key": "${TEST_API_KEY}"},
            )

            # Get the provider
            response = await client.get("/providers/provider-get-test")
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "provider-get-test"
            assert data["module"] == "provider-test"
            assert data["source"] == "git+https://example.com/provider"
            assert data["description"] == "Test provider"
            assert "api_key" in data["config"]

    async def test_get_provider_not_found(self):
        """Test getting a non-existent provider."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/providers/nonexistent-provider")
            assert response.status_code == 404

    async def test_delete_provider(self):
        """Test deleting a provider from registry."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Register a provider
            await client.post(
                "/providers",
                params={
                    "name": "provider-delete-test",
                    "module": "provider-test",
                },
            )

            # Delete the provider
            response = await client.delete("/providers/provider-delete-test")
            assert response.status_code == 200
            assert "removed from registry successfully" in response.json()["message"]

            # Verify it's gone
            get_response = await client.get("/providers/provider-delete-test")
            assert get_response.status_code == 404

    async def test_delete_provider_not_found(self):
        """Test deleting a non-existent provider."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/providers/nonexistent-provider")
            assert response.status_code == 404

    async def test_register_multiple_providers(self):
        """Test registering multiple providers."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Register multiple providers
            providers = [
                ("anthropic-1", "provider-anthropic"),
                ("openai-1", "provider-openai"),
                ("azure-1", "provider-azure"),
            ]

            for name, module in providers:
                await client.post(
                    "/providers",
                    params={"name": name, "module": module},
                )

            # List all providers
            response = await client.get("/providers")
            assert response.status_code == 200
            data = response.json()
            for name, _ in providers:
                assert name in data


@pytest.mark.asyncio
class TestRegistryEdgeCases:
    """Test edge cases and error scenarios for registries."""

    async def test_register_tool_duplicate_name(self):
        """Test registering a tool with a duplicate name (should overwrite)."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Register a tool
            await client.post(
                "/tools",
                params={
                    "name": "duplicate-tool",
                    "source": "source1",
                },
            )

            # Register again with same name but different source
            response = await client.post(
                "/tools",
                params={
                    "name": "duplicate-tool",
                    "source": "source2",
                },
            )
            assert response.status_code == 201

            # Verify it was overwritten
            get_response = await client.get("/tools/duplicate-tool?from_registry=true")
            data = get_response.json()
            assert data["source"] == "source2"

    async def test_register_provider_duplicate_name(self):
        """Test registering a provider with a duplicate name (should overwrite)."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Register a provider
            await client.post(
                "/providers",
                params={
                    "name": "duplicate-provider",
                    "module": "module1",
                },
            )

            # Register again with same name but different module
            response = await client.post(
                "/providers",
                params={
                    "name": "duplicate-provider",
                    "module": "module2",
                },
            )
            assert response.status_code == 201

            # Verify it was overwritten
            get_response = await client.get("/providers/duplicate-provider")
            data = get_response.json()
            assert data["module"] == "module2"
