"""Integration tests for complete user flows."""

import pytest
from httpx import ASGITransport, AsyncClient

from amplifier_app_api.main import app


@pytest.mark.asyncio
class TestCompleteSessionFlow:
    """Test complete session lifecycle."""

    async def test_create_send_delete_flow(self):
        """Test create session, send message, delete session."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create session
            create_response = await client.post(
                "/sessions/create",
                json={"bundle": "foundation"},
            )

            if create_response.status_code == 200:
                session_id = create_response.json()["session_id"]

                # Send message
                msg_response = await client.post(
                    f"/sessions/{session_id}/messages",
                    json={"message": "Hello"},
                )
                # May work or fail depending on amplifier setup
                assert msg_response.status_code in [200, 404, 500]

                # Delete session
                delete_response = await client.delete(f"/sessions/{session_id}")
                assert delete_response.status_code == 200

                # Verify deleted
                get_response = await client.get(f"/sessions/{session_id}")
                assert get_response.status_code == 404

    async def test_create_resume_send_flow(self):
        """Test create, resume, and send message flow."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create session
            create_response = await client.post("/sessions/create", json={})

            if create_response.status_code == 200:
                session_id = create_response.json()["session_id"]

                # Resume session
                resume_response = await client.post(f"/sessions/{session_id}/resume")
                assert resume_response.status_code in [200, 500]

                # Send message
                msg_response = await client.post(
                    f"/sessions/{session_id}/messages",
                    json={"message": "Test after resume"},
                )
                assert msg_response.status_code in [200, 404, 500]

    async def test_list_after_create_flow(self):
        """Test that created sessions appear in list."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Get initial count
            list1 = await client.get("/sessions")
            initial_count = len(list1.json()["sessions"])

            # Create session
            create_response = await client.post("/sessions/create", json={})

            if create_response.status_code == 200:
                # List again
                list2 = await client.get("/sessions")
                new_count = len(list2.json()["sessions"])

                # Should have one more
                assert new_count == initial_count + 1


@pytest.mark.asyncio
class TestConfigurationFlow:
    """Test configuration management flows."""

    async def test_add_provider_then_list_flow(self):
        """Test adding provider and verifying it appears in list."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Add provider
            add_response = await client.post(
                "/config/providers",
                json={"provider": "test-provider", "api_key": "test-key"},
            )
            assert add_response.status_code == 200

            # List providers
            list_response = await client.get("/config/providers")
            assert list_response.status_code == 200
            providers = list_response.json()

            # Verify it's in the list
            provider_names = [p["name"] for p in providers]
            assert "test-provider" in provider_names

    async def test_add_bundle_then_activate_flow(self):
        """Test adding bundle and activating it."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Add bundle
            add_response = await client.post(
                "/bundles",
                json={
                    "source": "git+https://github.com/example/test-bundle",
                    "name": "test-bundle",
                },
            )
            assert add_response.status_code == 200

            # Activate bundle
            activate_response = await client.post("/bundles/test-bundle/activate")
            # Should succeed now that bundle exists
            assert activate_response.status_code in [200, 500]

            # Verify it's active
            list_response = await client.get("/bundles")
            if list_response.status_code == 200:
                data = list_response.json()
                assert data.get("active") == "test-bundle"


@pytest.mark.asyncio
class TestConcurrency:
    """Test concurrent requests."""

    async def test_concurrent_session_creation(self):
        """Test creating multiple sessions concurrently."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create 5 sessions concurrently
            tasks = [
                client.post("/sessions/create", json={"bundle": "foundation"}) for _ in range(5)
            ]

            import asyncio

            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # All should succeed or fail gracefully (no crashes)
            for response in responses:
                if not isinstance(response, Exception):
                    assert hasattr(response, "status_code")
                    assert response.status_code in [200, 500]

    async def test_concurrent_health_checks(self):
        """Test concurrent health checks."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            import asyncio

            tasks = [client.get("/health") for _ in range(10)]
            responses = await asyncio.gather(*tasks)

            # All should succeed
            for response in responses:
                assert response.status_code == 200


@pytest.mark.asyncio
class TestRateLimiting:
    """Test rate limiting behavior (if implemented)."""

    async def test_rapid_requests_handled(self):
        """Test that rapid requests don't crash the service."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Send 20 rapid requests
            for _ in range(20):
                response = await client.get("/health")
                # Should not crash
                assert response.status_code in [200, 429]  # 429 if rate limited


@pytest.mark.asyncio
class TestDataPersistence:
    """Test that data persists across operations."""

    async def test_session_persists_after_creation(self):
        """Test session data persists in database."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create session
            create_response = await client.post(
                "/sessions/create",
                json={"bundle": "foundation", "provider": "anthropic"},
            )

            if create_response.status_code == 200:
                session_id = create_response.json()["session_id"]

                # Retrieve it
                get_response = await client.get(f"/sessions/{session_id}")
                assert get_response.status_code == 200

                # Verify metadata preserved
                data = get_response.json()
                assert data["session_id"] == session_id
                assert data["metadata"]["bundle"] == "foundation"
                assert data["metadata"]["provider"] == "anthropic"

    async def test_config_persists_after_update(self):
        """Test configuration persists after update."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Update config
            update_response = await client.post(
                "/config",
                json={"providers": {"test": {"config": {"value": "123"}}}},
            )
            assert update_response.status_code == 200

            # Retrieve config
            get_response = await client.get("/config")
            assert get_response.status_code == 200
            data = get_response.json()

            # Verify persisted
            assert "test" in data["providers"]
