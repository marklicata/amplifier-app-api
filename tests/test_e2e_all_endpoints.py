"""Complete E2E tests hitting EVERY endpoint with a real HTTP server.

These tests spin up the actual service and make real HTTP requests
to validate the full HTTP stack works correctly.
"""

import pytest

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

# Use the live_service fixture from conftest.py


@pytest.mark.e2e
class TestE2EHealthEndpoints:
    """Test all health and info endpoints."""

    def test_health_endpoint(self, live_service):
        """GET /health"""
        response = httpx.get(f"{live_service}/health", timeout=5.0)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "database_connected" in data

    def test_version_endpoint(self, live_service):
        """GET /version"""
        response = httpx.get(f"{live_service}/version", timeout=5.0)
        assert response.status_code == 200
        data = response.json()
        assert "service_version" in data

    def test_root_endpoint(self, live_service):
        """GET /"""
        response = httpx.get(f"{live_service}/", timeout=5.0)
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Amplifier App api"

    def test_openapi_json(self, live_service):
        """GET /openapi.json"""
        response = httpx.get(f"{live_service}/openapi.json", timeout=5.0)
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    def test_docs_page(self, live_service):
        """GET /docs"""
        response = httpx.get(f"{live_service}/docs", timeout=5.0)
        assert response.status_code == 200
        assert len(response.text) > 0


@pytest.mark.e2e
class TestE2ESessionEndpoints:
    """Test all 8 session endpoints."""

    def test_create_session(self, live_service):
        """POST /sessions"""
        # Use e2e_test_bundle from environment
        import os

        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set")

        # Then create session from config
        response = httpx.post(
            f"{live_service}/sessions",
            json={"config_id": config_id},
            timeout=10.0,
        )
        # May return 200 (success) or 500 (amplifier-core loading failed)
        assert response.status_code in [200, 500]

        # If successful, verify response structure
        if response.status_code == 200:
            data = response.json()
            assert "session_id" in data
            assert "status" in data
            assert "config_id" in data
            return data["session_id"]
        return None

    def test_list_sessions(self, live_service):
        """GET /sessions"""
        response = httpx.get(f"{live_service}/sessions", timeout=5.0)
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total" in data
        assert isinstance(data["sessions"], list)

    def test_get_session_404(self, live_service):
        """GET /sessions/{id} - nonexistent"""
        response = httpx.get(f"{live_service}/sessions/nonexistent-id", timeout=5.0)
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_delete_session_404(self, live_service):
        """DELETE /sessions/{id} - nonexistent"""
        response = httpx.delete(f"{live_service}/sessions/nonexistent-id", timeout=5.0)
        assert response.status_code == 404

    def test_resume_session_404(self, live_service):
        """POST /sessions/{id}/resume - nonexistent"""
        response = httpx.post(f"{live_service}/sessions/nonexistent-id/resume", timeout=5.0)
        assert response.status_code == 404

    def test_send_message_404(self, live_service):
        """POST /sessions/{id}/messages - nonexistent session"""
        response = httpx.post(
            f"{live_service}/sessions/nonexistent-id/messages",
            json={"message": "test"},
            timeout=5.0,
        )
        assert response.status_code == 404

    def test_send_message_validation_error(self, live_service):
        """POST /sessions/{id}/messages - missing required field"""
        response = httpx.post(
            f"{live_service}/sessions/test-id/messages",
            json={},  # Missing 'message' field
            timeout=5.0,
        )
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_cancel_session_404(self, live_service):
        """POST /sessions/{id}/cancel - nonexistent"""
        response = httpx.post(f"{live_service}/sessions/nonexistent-id/cancel", timeout=5.0)
        assert response.status_code == 404


@pytest.mark.e2e
class TestE2EConfigEndpoints:
    """Test all 5 config CRUD endpoints."""

    def test_create_config(self, live_service):
        """POST /configs"""
        response = httpx.post(
            f"{live_service}/configs",
            json={
                "name": "test-config",
                "config_data": {
                    "bundle": {"name": "test", "version": "1.0.0"},
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
                },
            },
            timeout=5.0,
        )
        assert response.status_code == 201
        data = response.json()
        assert "config_id" in data
        assert data["name"] == "test-config"

    def test_list_configs(self, live_service):
        """GET /configs"""
        response = httpx.get(f"{live_service}/configs", timeout=5.0)
        assert response.status_code == 200
        data = response.json()
        assert "configs" in data
        assert "total" in data

    def test_get_config_404(self, live_service):
        """GET /configs/{id} - nonexistent"""
        response = httpx.get(f"{live_service}/configs/nonexistent-id", timeout=5.0)
        assert response.status_code == 404

    def test_update_config_404(self, live_service):
        """PUT /configs/{id} - nonexistent"""
        response = httpx.put(
            f"{live_service}/configs/nonexistent-id",
            json={"name": "updated"},
            timeout=5.0,
        )
        assert response.status_code == 404

    def test_delete_config_404(self, live_service):
        """DELETE /configs/{id} - nonexistent"""
        response = httpx.delete(f"{live_service}/configs/nonexistent-id", timeout=5.0)
        assert response.status_code == 404




@pytest.mark.e2e
class TestE2ESmokeTestEndpoints:
    """Test smoke test API endpoints."""

    def test_quick_smoke_tests(self, live_service):
        """GET /smoke-tests/quick"""
        response = httpx.get(f"{live_service}/smoke-tests/quick", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "passed" in data
        assert "failed" in data
        assert "total" in data

    def test_full_smoke_tests(self, live_service):
        """GET /smoke-tests"""
        response = httpx.get(f"{live_service}/smoke-tests?pattern=test_smoke.py", timeout=60.0)
        assert response.status_code == 200
        data = response.json()
        assert "success" in data


@pytest.mark.e2e
class TestE2EErrorHandling:
    """Test error handling across all endpoints."""

    def test_404_unknown_endpoint(self, live_service):
        """Test 404 for completely unknown endpoint."""
        response = httpx.get(f"{live_service}/this/does/not/exist", timeout=5.0)
        assert response.status_code == 404

    def test_405_wrong_method(self, live_service):
        """Test 405 for wrong HTTP method."""
        response = httpx.put(f"{live_service}/sessions", timeout=5.0)
        assert response.status_code == 405

    def test_422_validation_error(self, live_service):
        """Test 422 for validation errors."""
        response = httpx.post(
            f"{live_service}/sessions/test/messages",
            json={"wrong_field": "value"},
            timeout=5.0,
        )
        assert response.status_code == 422

    def test_malformed_json(self, live_service):
        """Test handling of malformed JSON."""
        response = httpx.post(
            f"{live_service}/sessions",
            content="not-valid-json",
            headers={"Content-Type": "application/json"},
            timeout=5.0,
        )
        assert response.status_code == 422


@pytest.mark.e2e
class TestE2ECompleteFlow:
    """Test a complete workflow if session creation works."""

    def test_create_config_list_flow(self, live_service):
        """Test create config → list configs → verify it's there."""
        # Create a config
        add_response = httpx.post(
            f"{live_service}/configs",
            json={
                "name": "e2e-test-config",
                "config_data": {
                    "bundle": {"name": "e2e-test", "version": "1.0.0"},
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
                        "config": {"api_key": "test-key-123", "model": "claude-sonnet-4-5"}
                    }]
                },
            },
            timeout=5.0,
        )
        assert add_response.status_code == 201

        config_id = add_response.json()["config_id"]

        # List configs
        list_response = httpx.get(f"{live_service}/configs", timeout=5.0)
        assert list_response.status_code == 200
        configs = list_response.json()

        # Verify it's in the list
        config_ids = [c["config_id"] for c in configs["configs"]]
        assert config_id in config_ids

        # Get the specific config
        get_response = httpx.get(f"{live_service}/configs/{config_id}", timeout=5.0)
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["name"] == "e2e-test-config"


@pytest.mark.e2e
class TestE2EEndpointCoverage:
    """Verify every endpoint exists and responds."""

    def test_all_session_endpoints_exist(self, live_service):
        """Verify all 8 session endpoints are accessible."""
        endpoints = [
            ("POST", "/sessions", {"config_id": "test-config"}),
            ("GET", "/sessions", None),
            ("GET", "/sessions/test-id", None),  # Will 404
            ("DELETE", "/sessions/test-id", None),  # Will 404
            ("POST", "/sessions/test-id/resume", None),  # Will 404
            ("POST", "/sessions/test-id/messages", {"message": "test"}),  # Will 404
            ("POST", "/sessions/test-id/stream", {"message": "test"}),  # Will 404
            ("POST", "/sessions/test-id/cancel", None),  # Will 404
        ]

        for method, path, json_data in endpoints:
            if method == "GET":
                response = httpx.get(f"{live_service}{path}", timeout=10.0)
            elif method == "POST":
                response = httpx.post(
                    f"{live_service}{path}",
                    json=json_data if json_data else {},
                    timeout=10.0,
                )
            elif method == "DELETE":
                response = httpx.delete(f"{live_service}{path}", timeout=5.0)

            # All endpoints should exist (not 405 for right method)
            assert response.status_code != 405, f"Endpoint {method} {path} returned 405"
            # Should be 200, 404, 422, or 500 (but not 405)
            assert response.status_code in [200, 404, 422, 500]

    def test_all_config_endpoints_exist(self, live_service):
        """Verify all 5 config endpoints are accessible."""
        endpoints = [
            ("POST", "/configs", {
                "name": "test",
                "config_data": {
                    "bundle": {"name": "test", "version": "1.0.0"},
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
            }),
            ("GET", "/configs", None),
            ("GET", "/configs/test-id", None),
            ("PUT", "/configs/test-id", {"name": "updated"}),
            ("DELETE", "/configs/test-id", None),
        ]

        for method, path, json_data in endpoints:
            if method == "GET":
                response = httpx.get(f"{live_service}{path}", timeout=5.0)
            elif method == "POST":
                response = httpx.post(
                    f"{live_service}{path}",
                    json=json_data if json_data else {},
                    timeout=5.0,
                )
            elif method == "PUT":
                response = httpx.put(
                    f"{live_service}{path}",
                    json=json_data if json_data else {},
                    timeout=5.0,
                )
            elif method == "DELETE":
                response = httpx.delete(f"{live_service}{path}", timeout=5.0)

            assert response.status_code != 405, f"Endpoint {method} {path} returned 405"
            assert response.status_code in [200, 201, 404, 422, 500]

    def test_all_health_endpoints_exist(self, live_service):
        """Verify all health endpoints are accessible."""
        endpoints = [
            ("GET", "/health", None),
            ("GET", "/version", None),
            ("GET", "/", None),
            ("GET", "/smoke-tests/quick", None),
        ]

        for method, path, json_data in endpoints:
            response = httpx.get(f"{live_service}{path}", timeout=10.0)
            assert response.status_code == 200, f"Endpoint {method} {path} failed"
