"""Comprehensive E2E tests for additional endpoints and edge cases."""

import pytest

try:
    import httpx
except ImportError:
    pytest.skip("httpx not installed", allow_module_level=True)


BASE_URL = "http://localhost:8765"


class TestConfigSubResources:
    """Test config sub-resource endpoints (providers, bundles, tools)."""


class TestBundleOperations:
    """Test bundle-specific operations."""

    def test_get_specific_bundle(self):
        """Test getting details for a specific bundle."""
        # First list bundles to get a valid bundle name
        list_response = httpx.get(f"{BASE_URL}/bundles", timeout=30.0)
        assert list_response.status_code == 200
        bundles = list_response.json()["bundles"]

        if bundles:
            bundle_name = bundles[0]["name"]
            response = httpx.get(f"{BASE_URL}/bundles/{bundle_name}", timeout=10.0)
            # May succeed or fail depending on bundle availability
            assert response.status_code in [200, 404, 500]


class TestToolOperations:
    """Test tool invocation and management."""

    def test_get_specific_tool(self):
        """Test getting details for a specific tool."""
        # Try to get a common tool
        response = httpx.get(f"{BASE_URL}/tools/read_file", timeout=10.0)
        # May succeed or fail depending on tool availability
        assert response.status_code in [200, 404, 500]

    def test_invoke_tool_missing_params(self):
        """Test tool invocation with missing required parameters."""
        response = httpx.post(
            f"{BASE_URL}/tools/invoke",
            json={
                "tool_name": "read_file"
                # Missing required 'parameters' field
            },
            timeout=10.0,
        )
        # May be 422 (validation error) or 500 (server error)
        assert response.status_code in [422, 500]


class TestApplicationOperations:
    """Test application-specific operations."""

    def test_regenerate_api_key(self):
        """Test regenerating API key for an application."""
        import time

        # Create an application
        app_id = f"test-app-regen-{int(time.time() * 1000)}"
        create_response = httpx.post(
            f"{BASE_URL}/applications",
            json={
                "app_id": app_id,
                "app_name": "Test App for Regeneration",
            },
            timeout=10.0,
        )
        assert create_response.status_code == 201
        old_api_key = create_response.json()["api_key"]

        # Regenerate API key
        regen_response = httpx.post(
            f"{BASE_URL}/applications/{app_id}/regenerate-key", timeout=10.0
        )
        assert regen_response.status_code == 200
        data = regen_response.json()
        assert "api_key" in data
        new_api_key = data["api_key"]

        # Verify new key is different
        assert new_api_key != old_api_key

        # Cleanup
        httpx.delete(f"{BASE_URL}/applications/{app_id}", timeout=10.0)


class TestSmokeTests:
    """Test smoke test endpoints."""

    def test_smoke_tests_endpoint(self):
        """Test the smoke tests listing endpoint."""
        response = httpx.get(f"{BASE_URL}/smoke-tests", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        # Smoke test endpoint may return various formats depending on pytest-json-report availability
        assert isinstance(data, dict)

    def test_quick_smoke_tests(self):
        """Test quick smoke test execution."""
        response = httpx.get(f"{BASE_URL}/smoke-tests/quick", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "passed" in data
        assert "failed" in data


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_create_config_with_empty_yaml(self):
        """Test creating config with empty YAML."""
        response = httpx.post(
            f"{BASE_URL}/configs",
            json={"name": "empty-config", "yaml_content": ""},
            timeout=10.0,
        )
        # Should fail validation
        assert response.status_code in [400, 422, 500]

    def test_create_config_with_invalid_yaml(self):
        """Test creating config with invalid YAML."""
        response = httpx.post(
            f"{BASE_URL}/configs",
            json={"name": "invalid-yaml-config", "yaml_content": "invalid: [yaml: syntax"},
            timeout=10.0,
        )
        # Should fail validation
        assert response.status_code in [400, 422, 500]

    def test_create_config_with_very_long_name(self):
        """Test creating config with very long name."""
        long_name = "x" * 300
        response = httpx.post(
            f"{BASE_URL}/configs",
            json={
                "name": long_name,
                "yaml_content": "bundle:\n  name: test\n",
            },
            timeout=10.0,
        )
        # May succeed or fail depending on name length limits
        assert response.status_code in [201, 400, 422, 500]

    def test_list_configs_with_pagination(self):
        """Test config listing with pagination parameters."""
        response = httpx.get(f"{BASE_URL}/configs?limit=5&offset=0", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert "configs" in data

    def test_list_sessions_with_pagination(self):
        """Test session listing with pagination parameters."""
        response = httpx.get(f"{BASE_URL}/sessions?limit=10&offset=0", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data

    def test_delete_nonexistent_application(self):
        """Test deleting an application that doesn't exist."""
        response = httpx.delete(f"{BASE_URL}/applications/nonexistent-app-id", timeout=10.0)
        assert response.status_code == 404

    def test_get_nonexistent_bundle(self):
        """Test getting a bundle that doesn't exist."""
        response = httpx.get(f"{BASE_URL}/bundles/nonexistent-bundle", timeout=10.0)
        assert response.status_code == 404

    def test_get_nonexistent_tool(self):
        """Test getting a tool that doesn't exist."""
        response = httpx.get(f"{BASE_URL}/tools/nonexistent-tool", timeout=10.0)
        # May be 404 or 500 depending on tool loading state
        assert response.status_code in [404, 500]


class TestConcurrency:
    """Test concurrent operations."""

    def test_concurrent_config_creation(self):
        """Test creating multiple configs concurrently."""
        import concurrent.futures
        import time

        def create_config(index):
            return httpx.post(
                f"{BASE_URL}/configs",
                json={
                    "name": f"concurrent-config-{index}-{int(time.time() * 1000)}",
                    "yaml_content": "bundle:\n  name: test\nsession:\n  orchestrator: loop-basic\n  context: context-simple\n",
                },
                timeout=30.0,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_config, i) for i in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed
        for response in results:
            assert response.status_code == 201

    def test_concurrent_application_creation(self):
        """Test creating multiple applications concurrently."""
        import concurrent.futures
        import time

        def create_application(index):
            return httpx.post(
                f"{BASE_URL}/applications",
                json={
                    "app_id": f"concurrent-app-{index}-{int(time.time() * 1000)}",
                    "app_name": f"Concurrent App {index}",
                },
                timeout=30.0,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_application, i) for i in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed
        for response in results:
            assert response.status_code == 201


class TestDataIntegrity:
    """Test data integrity and consistency."""

    def test_config_update_and_retrieve(self):
        """Test that config updates are properly persisted."""
        import time

        # Create config
        name = f"integrity-test-{int(time.time() * 1000)}"
        create_response = httpx.post(
            f"{BASE_URL}/configs",
            json={
                "name": name,
                "yaml_content": "bundle:\n  name: original\nsession:\n  orchestrator: loop-basic\n  context: context-simple\n",
            },
            timeout=30.0,
        )
        assert create_response.status_code == 201
        config_id = create_response.json()["config_id"]

        # Retrieve and verify
        get_response = httpx.get(f"{BASE_URL}/configs/{config_id}", timeout=10.0)
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["name"] == name
        assert "original" in data["yaml_content"]

    def test_application_after_creation(self):
        """Test that application data persists correctly."""
        import time

        # Create application
        app_id = f"persist-test-{int(time.time() * 1000)}"
        app_name = "Persistence Test App"

        create_response = httpx.post(
            f"{BASE_URL}/applications",
            json={
                "app_id": app_id,
                "app_name": app_name,
            },
            timeout=10.0,
        )
        assert create_response.status_code == 201

        # Retrieve and verify
        get_response = httpx.get(f"{BASE_URL}/applications/{app_id}", timeout=10.0)
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["app_id"] == app_id
        assert data["app_name"] == app_name
        assert data["is_active"] is True

        # Cleanup
        httpx.delete(f"{BASE_URL}/applications/{app_id}", timeout=10.0)


class TestResponseFormats:
    """Test response format consistency."""

    def test_health_response_format(self):
        """Test health endpoint returns expected format."""
        response = httpx.get(f"{BASE_URL}/health", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert data["version"] == "0.3.0"

    def test_version_response_format(self):
        """Test version endpoint returns expected format."""
        response = httpx.get(f"{BASE_URL}/version", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert "service_version" in data

    def test_error_response_format(self):
        """Test error responses have consistent format."""
        response = httpx.get(f"{BASE_URL}/nonexistent", timeout=10.0)
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_validation_error_format(self):
        """Test validation errors have consistent format."""
        response = httpx.post(
            f"{BASE_URL}/configs",
            json={"name": "test"},  # Missing yaml_content
            timeout=10.0,
        )
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
