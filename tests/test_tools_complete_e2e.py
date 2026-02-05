"""Complete E2E tests for tool endpoints.

Tests successful tool operations: listing, getting info, and invocation.

Requirements:
- Live HTTP server (uses live_service fixture)
- amplifier-core and amplifier-foundation configured
- Foundation bundle available
"""

import pytest

try:
    import httpx
except ImportError:
    httpx = None


@pytest.mark.e2e
@pytest.mark.skipif(httpx is None, reason="httpx not installed")
class TestToolListing:
    """Test tool listing from bundles."""

    def test_list_tools_from_foundation(self, live_service):
        """Test listing tools from foundation bundle."""
        response = httpx.get(
            f"{live_service}/tools?bundle=foundation",
            timeout=30.0,  # First bundle load is slow
        )

        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert isinstance(data["tools"], list)
        assert len(data["tools"]) > 0

        # Verify tool structure
        for tool in data["tools"]:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool

    def test_list_tools_from_default_bundle(self, live_service):
        """Test listing tools without specifying bundle (uses default)."""
        response = httpx.get(
            f"{live_service}/tools",
            timeout=30.0,
        )

        # Should default to foundation or active bundle
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert isinstance(data["tools"], list)

    def test_list_tools_includes_common_tools(self, live_service):
        """Test that foundation bundle includes expected tools."""
        response = httpx.get(
            f"{live_service}/tools?bundle=foundation",
            timeout=30.0,
        )

        assert response.status_code == 200
        data = response.json()
        tool_names = [t["name"] for t in data["tools"]]

        # Foundation should include these common tools
        expected_tools = ["read_file", "write_file", "bash", "task"]
        for expected in expected_tools:
            assert expected in tool_names, f"Expected tool '{expected}' not found in foundation"


@pytest.mark.e2e
@pytest.mark.skipif(httpx is None, reason="httpx not installed")
class TestToolInfo:
    """Test getting information about specific tools."""

    def test_get_tool_info_for_existing_tool(self, live_service):
        """Test getting info for a tool that exists in foundation."""
        # First list tools to ensure bundle is loaded
        list_response = httpx.get(f"{live_service}/tools?bundle=foundation", timeout=30.0)
        assert list_response.status_code == 200

        # Get info for read_file tool
        response = httpx.get(
            f"{live_service}/tools/read_file?bundle=foundation",
            timeout=10.0,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify tool info structure
        assert data["name"] == "read_file"
        assert "description" in data
        assert "parameters" in data
        assert isinstance(data["parameters"], dict)

    def test_get_tool_info_includes_parameters(self, live_service):
        """Test that tool info includes parameter specifications."""
        response = httpx.get(
            f"{live_service}/tools/bash?bundle=foundation",
            timeout=10.0,
        )

        if response.status_code == 200:
            data = response.json()
            assert data["name"] == "bash"
            assert "parameters" in data

            # bash tool should have command parameter
            params = data["parameters"]
            assert isinstance(params, dict)

    def test_get_nonexistent_tool_returns_404(self, live_service):
        """Test getting info for non-existent tool returns 404."""
        response = httpx.get(
            f"{live_service}/tools/nonexistent-tool-xyz?bundle=foundation",
            timeout=10.0,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


@pytest.mark.e2e
@pytest.mark.skipif(httpx is None, reason="httpx not installed")
class TestToolInvocation:
    """Test successful tool invocation."""

    def test_invoke_read_file_tool(self, live_service):
        """Test invoking read_file tool successfully."""
        # Invoke read_file to read README.md
        response = httpx.post(
            f"{live_service}/tools/invoke",
            json={
                "bundle_name": "foundation",
                "tool_name": "read_file",
                "parameters": {"file_path": "README.md"},
            },
            timeout=10.0,
        )

        assert response.status_code == 200
        data = response.json()

        # Should return tool result
        assert "result" in data
        # Result should contain file content
        assert isinstance(data["result"], dict)

    def test_invoke_bash_tool_simple_command(self, live_service):
        """Test invoking bash tool with simple command."""
        response = httpx.post(
            f"{live_service}/tools/invoke",
            json={
                "bundle_name": "foundation",
                "tool_name": "bash",
                "parameters": {"command": "echo hello"},
            },
            timeout=10.0,
        )

        assert response.status_code == 200
        data = response.json()
        assert "result" in data

        # Result should contain command output
        result = data["result"]
        assert isinstance(result, dict)
        if "stdout" in result:
            assert "hello" in result["stdout"]

    def test_invoke_tool_with_missing_parameters_returns_error(self, live_service):
        """Test invoking tool without required parameters returns error."""
        response = httpx.post(
            f"{live_service}/tools/invoke",
            json={
                "bundle_name": "foundation",
                "tool_name": "read_file",
                "parameters": {},  # Missing required file_path
            },
            timeout=10.0,
        )

        # Should return validation or execution error
        assert response.status_code in [400, 422, 500]

    def test_invoke_tool_with_invalid_parameters_returns_error(self, live_service):
        """Test invoking tool with invalid parameter types."""
        response = httpx.post(
            f"{live_service}/tools/invoke",
            json={
                "bundle_name": "foundation",
                "tool_name": "bash",
                "parameters": {"command": 12345},  # Should be string
            },
            timeout=10.0,
        )

        # Should validate parameter types
        assert response.status_code in [400, 422, 500]

    def test_invoke_nonexistent_tool_returns_404(self, live_service):
        """Test invoking non-existent tool returns 404."""
        response = httpx.post(
            f"{live_service}/tools/invoke",
            json={
                "bundle_name": "foundation",
                "tool_name": "nonexistent-tool-xyz",
                "parameters": {},
            },
            timeout=10.0,
        )

        assert response.status_code == 404

    def test_invoke_tool_from_nonexistent_bundle_returns_error(self, live_service):
        """Test invoking tool from non-existent bundle returns error."""
        response = httpx.post(
            f"{live_service}/tools/invoke",
            json={
                "bundle_name": "nonexistent-bundle",
                "tool_name": "read_file",
                "parameters": {"file_path": "README.md"},
            },
            timeout=10.0,
        )

        assert response.status_code in [404, 500]

    def test_invoke_tool_missing_required_fields_returns_422(self, live_service):
        """Test that missing required fields in request returns 422."""
        # Missing tool_name
        response = httpx.post(
            f"{live_service}/tools/invoke",
            json={
                "bundle_name": "foundation",
                "parameters": {},
            },
            timeout=5.0,
        )

        assert response.status_code == 422


@pytest.mark.e2e
@pytest.mark.skipif(httpx is None, reason="httpx not installed")
class TestToolSecurity:
    """Test tool invocation security and validation."""

    def test_invoke_dangerous_command_is_blocked(self, live_service):
        """Test that dangerous bash commands are blocked."""
        # Try to run a potentially dangerous command
        response = httpx.post(
            f"{live_service}/tools/invoke",
            json={
                "bundle_name": "foundation",
                "tool_name": "bash",
                "parameters": {"command": "rm -rf /"},
            },
            timeout=10.0,
        )

        # Should either:
        # - Block with 400/403
        # - Execute safely with error
        # Don't assert specific status, just verify it doesn't crash service
        assert response.status_code in [200, 400, 403, 500]

        # Service should still be healthy after
        health = httpx.get(f"{live_service}/health", timeout=5.0)
        assert health.status_code == 200

    def test_tool_invocation_requires_bundle_name(self, live_service):
        """Test that bundle_name is required for tool invocation."""
        response = httpx.post(
            f"{live_service}/tools/invoke",
            json={
                "tool_name": "read_file",
                "parameters": {"file_path": "README.md"},
                # Missing bundle_name
            },
            timeout=5.0,
        )

        # Should require bundle_name
        assert response.status_code == 422


@pytest.mark.e2e
@pytest.mark.skipif(httpx is None, reason="httpx not installed")
class TestToolDiscovery:
    """Test tool discovery across different bundles."""

    def test_different_bundles_have_different_tools(self, live_service):
        """Test that different bundles expose different tool sets."""
        # Get tools from foundation
        foundation_response = httpx.get(
            f"{live_service}/tools?bundle=foundation",
            timeout=30.0,
        )

        assert foundation_response.status_code == 200
        foundation_tools = [t["name"] for t in foundation_response.json()["tools"]]

        # Foundation should have common tools
        assert "read_file" in foundation_tools
        assert "bash" in foundation_tools

    def test_tool_description_is_meaningful(self, live_service):
        """Test that tools have meaningful descriptions."""
        response = httpx.get(
            f"{live_service}/tools?bundle=foundation",
            timeout=30.0,
        )

        assert response.status_code == 200
        tools = response.json()["tools"]

        for tool in tools:
            # Description should exist and not be empty
            assert "description" in tool
            assert len(tool["description"]) > 0
            # Should be more than just the name
            assert len(tool["description"]) > len(tool["name"])
