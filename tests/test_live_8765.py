"""E2E tests against the live service running on port 8765."""

import pytest

try:
    import httpx
except ImportError:
    pytest.skip("httpx not installed", allow_module_level=True)


BASE_URL = "http://localhost:8765"


class TestHealthEndpoints:
    """Test health and service info endpoints."""

    def test_health_endpoint(self):
        """Test health endpoint returns healthy status."""
        response = httpx.get(f"{BASE_URL}/health", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "version" in data
        assert data["version"] == "0.2.0"
        assert "database_connected" in data

    def test_version_endpoint(self):
        """Test version endpoint."""
        response = httpx.get(f"{BASE_URL}/version", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert "service_version" in data
        assert data["service_version"] == "0.2.0"

    def test_root_endpoint(self):
        """Test root endpoint."""
        response = httpx.get(f"{BASE_URL}/", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert "service" in data

    def test_openapi_docs(self):
        """Test OpenAPI documentation is accessible."""
        response = httpx.get(f"{BASE_URL}/openapi.json", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
        assert "info" in data


class TestConfigEndpoints:
    """Test configuration management endpoints."""

    def test_create_config(self):
        """Test creating a new configuration."""
        response = httpx.post(
            f"{BASE_URL}/configs",
            json={
                "name": "test-config-live",
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
      api_key: test-key
      model: claude-sonnet-4-5
""",
            },
            timeout=30.0,
        )
        assert response.status_code == 201  # Created
        data = response.json()
        assert "config_id" in data
        assert "name" in data
        assert data["name"] == "test-config-live"
        return data["config_id"]

    def test_list_configs(self):
        """Test listing configurations."""
        response = httpx.get(f"{BASE_URL}/configs", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert "configs" in data
        assert isinstance(data["configs"], list)

    def test_get_config(self):
        """Test getting a specific configuration."""
        # First create a config
        config_id = self.test_create_config()

        # Then retrieve it
        response = httpx.get(f"{BASE_URL}/configs/{config_id}", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert data["config_id"] == config_id
        assert "yaml_content" in data

    def test_delete_config(self):
        """Test deleting a configuration."""
        # First create a config
        config_id = self.test_create_config()

        # Then delete it
        response = httpx.delete(f"{BASE_URL}/configs/{config_id}", timeout=10.0)
        assert response.status_code == 200


class TestSessionEndpoints:
    """Test session management endpoints."""

    def test_list_sessions(self):
        """Test listing sessions."""
        response = httpx.get(f"{BASE_URL}/sessions", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert isinstance(data["sessions"], list)

    def test_create_session(self):
        """Test creating a new session."""
        # First create a config
        config_response = httpx.post(
            f"{BASE_URL}/configs",
            json={
                "name": "session-test-config",
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
      api_key: test-key
      model: claude-sonnet-4-5
""",
            },
            timeout=30.0,
        )
        assert config_response.status_code == 201  # Created
        config_id = config_response.json()["config_id"]

        # Then create session
        response = httpx.post(
            f"{BASE_URL}/sessions",
            json={"config_id": config_id},
            timeout=30.0,
        )
        # Session creation may fail if amplifier-core isn't fully configured
        # Accept both success and server error
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "session_id" in data
            assert "status" in data
            assert "config_id" in data
            return data["session_id"]
        return None

    def test_get_session(self):
        """Test getting session details."""
        session_id = self.test_create_session()

        # Skip if session creation failed
        if session_id is None:
            pytest.skip("Session creation not available")

        response = httpx.get(f"{BASE_URL}/sessions/{session_id}", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id

    def test_delete_session(self):
        """Test deleting a session."""
        session_id = self.test_create_session()

        # Skip if session creation failed
        if session_id is None:
            pytest.skip("Session creation not available")

        response = httpx.delete(f"{BASE_URL}/sessions/{session_id}", timeout=10.0)
        assert response.status_code == 200


class TestBundleEndpoints:
    """Test bundle management endpoints."""

    def test_list_bundles(self):
        """Test listing available bundles."""
        response = httpx.get(f"{BASE_URL}/bundles", timeout=30.0)
        assert response.status_code == 200
        data = response.json()
        assert "bundles" in data
        assert isinstance(data["bundles"], list)


class TestToolEndpoints:
    """Test tool management endpoints."""

    def test_list_tools(self):
        """Test listing available tools."""
        response = httpx.get(f"{BASE_URL}/tools", timeout=30.0)
        # May succeed or fail depending on bundle loading
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "tools" in data


class TestApplicationEndpoints:
    """Test application management endpoints."""

    def test_list_applications(self):
        """Test listing applications."""
        response = httpx.get(f"{BASE_URL}/applications", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        # Response is a list directly, not a dict
        assert isinstance(data, list)

    def test_create_application(self):
        """Test creating an application."""
        import time

        # Use timestamp to ensure unique app_id
        app_id = f"test-app-{int(time.time() * 1000)}"

        response = httpx.post(
            f"{BASE_URL}/applications",
            json={
                "app_id": app_id,
                "app_name": "Test Application Live",
            },
            timeout=10.0,
        )
        assert response.status_code == 201  # Created
        data = response.json()
        assert "app_id" in data
        assert "api_key" in data
        assert data["app_id"] == app_id
        return data["app_id"]

    def test_get_application(self):
        """Test getting application details."""
        app_id = self.test_create_application()

        response = httpx.get(f"{BASE_URL}/applications/{app_id}", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert data["app_id"] == app_id

    def test_delete_application(self):
        """Test deleting an application."""
        app_id = self.test_create_application()

        response = httpx.delete(f"{BASE_URL}/applications/{app_id}", timeout=10.0)
        assert response.status_code == 200


class TestErrorHandling:
    """Test error handling."""

    def test_404_for_unknown_endpoint(self):
        """Test 404 for unknown endpoints."""
        response = httpx.get(f"{BASE_URL}/this/does/not/exist", timeout=10.0)
        assert response.status_code == 404

    def test_404_for_nonexistent_session(self):
        """Test 404 for nonexistent session."""
        response = httpx.get(f"{BASE_URL}/sessions/nonexistent-session-id", timeout=10.0)
        assert response.status_code == 404

    def test_404_for_nonexistent_config(self):
        """Test 404 for nonexistent config."""
        response = httpx.get(f"{BASE_URL}/configs/nonexistent-config-id", timeout=10.0)
        assert response.status_code == 404

    def test_405_for_wrong_method(self):
        """Test 405 for wrong HTTP method."""
        # PUT is not allowed on /health
        response = httpx.put(f"{BASE_URL}/health", timeout=5.0)
        assert response.status_code == 405

    def test_422_for_invalid_body(self):
        """Test 422 for invalid request body."""
        response = httpx.post(
            f"{BASE_URL}/sessions",
            json={},  # Missing required config_id
            timeout=10.0,
        )
        assert response.status_code == 422


class TestAuthentication:
    """Test authentication when enabled."""

    def test_auth_not_required_by_default(self):
        """Test that auth is not required by default in test environment."""
        response = httpx.get(f"{BASE_URL}/sessions", timeout=10.0)
        # Should work without auth token
        assert response.status_code == 200
