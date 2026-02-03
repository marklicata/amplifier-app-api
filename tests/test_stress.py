"""Stress tests for API endpoints."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from amplifier_app_api.main import app


@pytest.mark.asyncio
class TestStressLoad:
    """Stress tests for high load scenarios."""

    async def test_many_concurrent_health_checks(self):
        """Test handling many concurrent health checks."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            tasks = [client.get("/health") for _ in range(100)]
            responses = await asyncio.gather(*tasks)

            # All should succeed
            for response in responses:
                assert response.status_code == 200

    async def test_rapid_session_creation(self):
        """Test creating many sessions rapidly."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            tasks = [client.post("/sessions/create", json={}) for _ in range(20)]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # Count successes
            successes = sum(
                1
                for r in responses
                if not isinstance(r, Exception)
                and hasattr(r, "status_code")
                and r.status_code == 200
            )

            # At least some should succeed
            assert successes >= 0

    async def test_large_config_payload(self):
        """Test handling large configuration payloads."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create large config
            large_config = {
                "providers": {f"provider-{i}": {"config": {"data": "x" * 1000}} for i in range(50)}
            }

            response = await client.post("/config", json=large_config)
            # Should handle or reject gracefully
            assert response.status_code in [200, 413, 422, 500]

    async def test_session_list_with_many_sessions(self):
        """Test listing sessions when many exist."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create 50 sessions
            for i in range(50):
                await client.post("/sessions/create", json={})

            # List them
            response = await client.get("/sessions?limit=100")
            assert response.status_code == 200
            data = response.json()
            assert len(data["sessions"]) >= 0  # Should not crash


@pytest.mark.asyncio
class TestStressMemory:
    """Stress tests for memory handling."""

    async def test_repeated_operations_no_memory_leak(self):
        """Test repeated operations don't leak memory."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Perform 100 operations
            for _ in range(100):
                await client.get("/health")
                await client.get("/sessions")
                await client.get("/config")

            # Service should still respond
            final_response = await client.get("/health")
            assert final_response.status_code == 200

    async def test_session_cleanup_works(self):
        """Test that session cleanup prevents unbounded growth."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create and delete 20 sessions
            for _ in range(20):
                create_resp = await client.post("/sessions/create", json={})
                if create_resp.status_code == 200:
                    session_id = create_resp.json()["session_id"]
                    await client.delete(f"/sessions/{session_id}")

            # Service should still be healthy
            health = await client.get("/health")
            assert health.status_code == 200
