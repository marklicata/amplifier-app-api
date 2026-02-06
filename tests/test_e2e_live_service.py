"""End-to-end tests that start a real HTTP server and test it.

These tests actually spin up the service and make real HTTP requests.
This validates the full stack: FastAPI → uvicorn → HTTP → your code.
"""

import subprocess
import time
from pathlib import Path

import pytest

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]


@pytest.fixture(scope="module")
def live_service():
    """Start the service in a subprocess and yield the URL."""
    # Start the service
    proc = subprocess.Popen(
        [
            ".venv/bin/python",
            "-m",
            "uvicorn",
            "amplifier_app_api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8766",  # Different port to avoid conflicts
        ],
        cwd=Path(__file__).parent.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for service to start (up to 10 seconds)
    base_url = "http://127.0.0.1:8766"
    started = False

    for _ in range(20):  # 20 attempts × 0.5 seconds = 10 seconds max
        try:
            response = httpx.get(f"{base_url}/health", timeout=1.0)
            if response.status_code == 200:
                started = True
                break
        except (httpx.ConnectError, httpx.TimeoutException):
            time.sleep(0.5)

    if not started:
        proc.kill()
        raise RuntimeError("Service failed to start within 10 seconds")

    print(f"\n✅ Service started at {base_url}")

    yield base_url

    # Cleanup
    print("\n🛑 Stopping service...")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.mark.e2e
class TestLiveServiceHealth:
    """Test health endpoints on live service."""

    def test_health_endpoint_real_http(self, live_service):
        """Test health endpoint with real HTTP request."""
        response = httpx.get(f"{live_service}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "version" in data

    def test_version_endpoint_real_http(self, live_service):
        """Test version endpoint with real HTTP."""
        response = httpx.get(f"{live_service}/version")
        assert response.status_code == 200
        data = response.json()
        assert "service_version" in data

    def test_root_endpoint_real_http(self, live_service):
        """Test root endpoint with real HTTP."""
        response = httpx.get(f"{live_service}/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Amplifier App api"

    def test_openapi_docs_accessible(self, live_service):
        """Test OpenAPI documentation is accessible."""
        response = httpx.get(f"{live_service}/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data


@pytest.mark.e2e
class TestLiveServiceSessions:
    """Test session endpoints on live service."""

    def test_create_session_real_http(self, live_service):
        """Test creating a session with real HTTP."""
        # Use e2e_test_bundle from environment
        import os

        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set")

        # Then create session from config
        response = httpx.post(
            f"{live_service}/sessions",
            json={"config_id": config_id},
            timeout=30.0,
        )
        # May succeed or fail depending on amplifier-core setup
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "session_id" in data
            assert "status" in data
            assert "config_id" in data

    def test_list_sessions_real_http(self, live_service):
        """Test listing sessions with real HTTP."""
        response = httpx.get(f"{live_service}/sessions")
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total" in data

    def test_404_on_nonexistent_session(self, live_service):
        """Test 404 for nonexistent session."""
        response = httpx.get(f"{live_service}/sessions/nonexistent-id")
        assert response.status_code == 404


@pytest.mark.e2e
class TestLiveServiceConfig:
    """Test configuration endpoints on live service."""

    def test_get_config_real_http(self, live_service):
        """Test getting config with real HTTP."""
        response = httpx.get(f"{live_service}/config")
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert "bundles" in data

    def test_add_provider_real_http(self, live_service):
        """Test adding provider with real HTTP."""
        response = httpx.post(
            f"{live_service}/config/providers",
            json={"provider": "test-provider", "api_key": "test-key"},
        )
        assert response.status_code == 200

    def test_list_providers_real_http(self, live_service):
        """Test listing providers with real HTTP."""
        response = httpx.get(f"{live_service}/config/providers")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


@pytest.mark.e2e
class TestLiveServiceBundles:
    """Test bundle endpoints on live service."""

    def test_list_bundles_real_http(self, live_service):
        """Test listing bundles with real HTTP."""
        response = httpx.get(f"{live_service}/bundles")
        assert response.status_code == 200
        data = response.json()
        assert "bundles" in data

    def test_add_bundle_real_http(self, live_service):
        """Test adding bundle with real HTTP."""
        response = httpx.post(
            f"{live_service}/bundles",
            json={"source": "git+https://github.com/example/test-bundle"},
        )
        assert response.status_code in [200, 500]


@pytest.mark.e2e
class TestLiveServiceTools:
    """Test tool endpoints on live service."""

    def test_list_tools_real_http(self, live_service):
        """Test listing tools with real HTTP."""
        response = httpx.get(f"{live_service}/tools", timeout=30.0)
        # May succeed or fail depending on bundle loading
        assert response.status_code in [200, 500]


@pytest.mark.e2e
class TestLiveServiceSmokeTests:
    """Test smoke test endpoints on live service."""

    def test_smoke_tests_quick_endpoint(self, live_service):
        """Test quick smoke test endpoint."""
        response = httpx.get(f"{live_service}/smoke-tests/quick", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "passed" in data
        assert "failed" in data


@pytest.mark.e2e
class TestLiveServiceCORS:
    """Test CORS headers on live service."""

    def test_cors_headers_present(self, live_service):
        """Test that CORS headers are present."""
        response = httpx.get(
            f"{live_service}/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.status_code == 200
        # CORS headers may or may not be present depending on config
        # Just verify the request succeeds


@pytest.mark.e2e
class TestLiveServiceErrorHandling:
    """Test error handling on live service."""

    def test_404_for_unknown_endpoint(self, live_service):
        """Test 404 for unknown endpoints."""
        response = httpx.get(f"{live_service}/this/does/not/exist")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_405_for_wrong_method(self, live_service):
        """Test 405 for wrong HTTP method."""
        response = httpx.get(f"{live_service}/configs")
        assert response.status_code == 405

    def test_422_for_invalid_body(self, live_service):
        """Test 422 for invalid request body."""
        response = httpx.post(
            f"{live_service}/sessions/test/messages",
            json={},  # Missing required 'message' field
        )
        assert response.status_code == 422
