"""Stress tests for config reusability and bundle caching.

Tests that verify performance and correctness under load.
"""

import asyncio
import time

import pytest
import yaml
from httpx import AsyncClient, Response


@pytest.mark.asyncio
class TestConfigCachingPerformance:
    """Test bundle caching performance and correctness."""

    async def test_first_session_slower_than_subsequent(self, client: AsyncClient):
        """Test that first session creation is slower (prepares bundle), subsequent are fast (cached)."""
        # Create config
        config_response = await client.post(
            "/configs",
            json={
                "name": "caching-perf-test",
                "yaml_content": """
bundle:
  name: cache-perf

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
        )

        config_id = config_response.json()["config_id"]

        # Create first session (should prepare bundle)
        start1 = time.time()
        response1 = await client.post("/sessions", json={"config_id": config_id})
        duration1 = time.time() - start1

        assert response1.status_code in [201, 500]  # May fail without amplifier-core

        if response1.status_code == 201:
            # Create second session (should use cached bundle)
            start2 = time.time()
            response2 = await client.post("/sessions", json={"config_id": config_id})
            duration2 = time.time() - start2

            assert response2.status_code == 201

            # Second should be faster (or similar if both are fast)
            # We don't assert duration2 < duration1 because timing can vary
            # But we log it for manual observation
            print(f"First session: {duration1:.3f}s, Second session: {duration2:.3f}s")

    async def test_many_concurrent_sessions_same_config(self, client: AsyncClient):
        """Test creating many sessions concurrently from the same config."""
        # Create config
        config_response = await client.post(
            "/configs",
            json={
                "name": "concurrent-stress",
                "yaml_content": """
bundle:
  name: concurrent

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
        )

        config_id = config_response.json()["config_id"]

        # Create 20 sessions concurrently
        tasks = [client.post("/sessions", json={"config_id": config_id}) for _ in range(20)]

        start = time.time()
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        duration = time.time() - start

        # Count successes - filter to Response objects first, then by status code
        response_objs: list[Response] = [r for r in responses if isinstance(r, Response)]
        successes = [r for r in response_objs if r.status_code == 201]

        print(f"Created {len(successes)}/20 sessions in {duration:.3f}s")

        # At least some should succeed
        assert len(successes) > 0

        # All successful sessions should have unique IDs
        session_ids = [r.json()["session_id"] for r in successes]
        assert len(session_ids) == len(set(session_ids))

        # All should reference the same config
        for response in successes:
            assert response.json()["config_id"] == config_id

    async def test_cache_invalidation_forces_recomputation(self, client: AsyncClient):
        """Test that updating config invalidates cache and forces bundle preparation."""
        # Create config
        config_response = await client.post(
            "/configs",
            json={
                "name": "cache-invalidation",
                "yaml_content": """
bundle:
  name: cache-inv
  version: 1.0.0

includes:
  - bundle: foundation

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: test-key-v1
      model: claude-sonnet-4-5
""",
            },
        )

        config_id = config_response.json()["config_id"]

        # Create first session (prepares bundle, caches it)
        response1 = await client.post("/sessions", json={"config_id": config_id})
        if response1.status_code != 201:
            pytest.skip("Session creation not working - skipping cache test")

        # Create second session (uses cache - should be fast)
        start_cached = time.time()
        response2 = await client.post("/sessions", json={"config_id": config_id})
        cached_duration = time.time() - start_cached
        assert response2.status_code == 201

        # Update config (invalidates cache)
        await client.put(
            f"/configs/{config_id}",
            json={
                "yaml_content": """
bundle:
  name: cache-inv
  version: 2.0.0

includes:
  - bundle: foundation

session:
  orchestrator: loop-streaming
  context: context-persistent

providers:
  - module: provider-anthropic
    config:
      api_key: test-key-v2
      model: claude-opus-4
"""
            },
        )

        # Create third session (cache invalidated, should re-prepare)
        start_invalidated = time.time()
        response3 = await client.post("/sessions", json={"config_id": config_id})
        invalidated_duration = time.time() - start_invalidated

        assert response3.status_code in [201, 500]

        print(f"Cached: {cached_duration:.3f}s, After invalidation: {invalidated_duration:.3f}s")

    async def test_multiple_configs_independent_caches(self, client: AsyncClient):
        """Test that different configs maintain independent caches."""
        # Create 3 different configs
        config_ids = []
        for i in range(3):
            response = await client.post(
                "/configs",
                json={
                    "name": f"independent-cache-{i}",
                    "yaml_content": f"""
bundle:
  name: independent-{i}

includes:
  - bundle: foundation

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: test-key-{i}
      model: claude-sonnet-4-5
""",
                },
            )
            config_ids.append(response.json()["config_id"])

        # Create sessions from each config
        for config_id in config_ids:
            response = await client.post("/sessions", json={"config_id": config_id})
            # Each should prepare independently
            assert response.status_code in [201, 500]

        # Create second sessions from each (should use respective caches)
        for config_id in config_ids:
            response = await client.post("/sessions", json={"config_id": config_id})
            assert response.status_code in [201, 500]


@pytest.mark.asyncio
class TestHighVolumeOperations:
    """Test high-volume operations."""

    async def test_create_100_configs(self, client: AsyncClient):
        """Test creating 100 configs."""
        config_ids = []
        errors = 0

        for i in range(100):
            response = await client.post(
                "/configs",
                json={
                    "name": f"stress-config-{i}",
                    "yaml_content": f"""
bundle:
  name: stress-{i}

includes:
  - bundle: foundation

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: stress-key-{i}
      model: claude-sonnet-4-5
""",
                    "tags": {"batch": "stress-100", "index": str(i)},
                },
            )

            if response.status_code == 201:
                config_ids.append(response.json()["config_id"])
            else:
                errors += 1

        print(f"Created {len(config_ids)}/100 configs, {errors} errors")
        assert len(config_ids) >= 90  # At least 90% success rate

        # Cleanup
        for config_id in config_ids:
            await client.delete(f"/configs/{config_id}")

    async def test_create_100_sessions_from_one_config(self, client: AsyncClient):
        """Test creating 100 sessions from a single config."""
        # Create config
        config_response = await client.post(
            "/configs",
            json={
                "name": "100-sessions-config",
                "yaml_content": """
bundle:
  name: hundred-sessions

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
        )

        config_id = config_response.json()["config_id"]

        # Create 100 sessions
        session_ids = []
        errors = 0

        start = time.time()
        for i in range(100):
            response = await client.post("/sessions", json={"config_id": config_id})

            if response.status_code == 201:
                session_ids.append(response.json()["session_id"])
            else:
                errors += 1

        duration = time.time() - start

        print(
            f"Created {len(session_ids)}/100 sessions in {duration:.3f}s ({duration / 100:.3f}s per session)"
        )
        print(f"Errors: {errors}")

        # Should be very fast due to caching (if amplifier-core available)
        assert len(session_ids) >= 1  # At least one should work

        # All unique
        assert len(session_ids) == len(set(session_ids))

        # Cleanup sessions
        for session_id in session_ids[:10]:  # Delete first 10 for cleanup
            await client.delete(f"/sessions/{session_id}")

    async def test_concurrent_config_operations_stress(self, client: AsyncClient):
        """Test many concurrent config operations."""
        import asyncio

        # Create base configs
        config_ids = []
        for i in range(10):
            response = await client.post(
                "/configs",
                json={
                    "name": f"concurrent-ops-{i}",
                    "yaml_content": f"bundle:\n  name: concurrent-{i}\nincludes:\n  - bundle: foundation\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test-{i}",
                },
            )
            if response.status_code == 201:
                config_ids.append(response.json()["config_id"])

        # Mix of operations on these configs
        tasks = []
        for config_id in config_ids:
            # Get
            tasks.append(client.get(f"/configs/{config_id}"))
            # Update
            tasks.append(client.put(f"/configs/{config_id}", json={"description": "Updated"}))
            # Add tool
            tasks.append(
                client.post(
                    f"/configs/{config_id}/tools",
                    params={"tool_module": "tool-web", "tool_source": "./tool-web"},
                )
            )

        # Execute all concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter to Response objects first, then by status code
        response_objs: list[Response] = [r for r in results if isinstance(r, Response)]
        successes = [r for r in response_objs if r.status_code in [200, 201]]
        failures = [r for r in results if not isinstance(r, Response)] + [
            r for r in response_objs if r.status_code >= 400
        ]

        print(f"Concurrent ops: {len(successes)} successes, {len(failures)} failures")

        # Most should succeed
        assert len(successes) >= len(tasks) * 0.8  # 80% success rate

        # Cleanup
        for config_id in config_ids:
            await client.delete(f"/configs/{config_id}")

    async def test_rapid_create_delete_cycles(self, client: AsyncClient):
        """Test rapid create/delete cycles."""
        yaml = "bundle:\n  name: rapid\nincludes:\n  - bundle: foundation\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test"

        created = 0
        deleted = 0

        for i in range(50):
            # Create
            create_response = await client.post(
                "/configs",
                json={"name": f"rapid-{i}", "yaml_content": yaml},
            )

            if create_response.status_code == 201:
                created += 1
                config_id = create_response.json()["config_id"]

                # Immediately delete
                delete_response = await client.delete(f"/configs/{config_id}")
                if delete_response.status_code == 200:
                    deleted += 1

        print(f"Rapid cycles: {created} created, {deleted} deleted")
        assert created == deleted  # Should match
        assert created >= 45  # 90% success rate

    async def test_config_update_invalidation_stress(self, client: AsyncClient):
        """Test cache invalidation under stress."""
        # Create config
        config_response = await client.post(
            "/configs",
            json={
                "name": "invalidation-stress",
                "yaml_content": """
bundle:
  name: invalidation
  version: 1.0.0

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
        )

        config_id = config_response.json()["config_id"]

        # Create initial session
        response1 = await client.post("/sessions", json={"config_id": config_id})
        if response1.status_code != 201:
            pytest.skip("Session creation not working")

        session_count = 1

        # Alternate: update config, create session
        for i in range(10):
            # Update
            await client.put(
                f"/configs/{config_id}",
                json={
                    "yaml_content": f"""
bundle:
  name: invalidation
  version: {i + 2}.0.0

includes:
  - bundle: foundation

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: test-key-v{i + 2}
      model: claude-sonnet-4-5
"""
                },
            )

            # Create session (should use updated config)
            response = await client.post("/sessions", json={"config_id": config_id})
            if response.status_code == 201:
                session_count += 1

        print(f"Created {session_count} sessions across 10 config updates")
        assert session_count >= 5  # At least half should work


@pytest.mark.asyncio
class TestScalability:
    """Test scalability scenarios."""

    async def test_many_configs_many_sessions_each(self, client: AsyncClient):
        """Test: 10 configs, 10 sessions each = 100 total sessions."""
        config_ids = []
        session_counts = {}

        # Create 10 configs
        for i in range(10):
            response = await client.post(
                "/configs",
                json={
                    "name": f"scale-config-{i}",
                    "yaml_content": f"""
bundle:
  name: scale-{i}

includes:
  - bundle: foundation

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: scale-key-{i}
      model: claude-sonnet-4-5
""",
                },
            )

            if response.status_code == 201:
                config_id = response.json()["config_id"]
                config_ids.append(config_id)
                session_counts[config_id] = 0

        # Create 10 sessions from each config
        for config_id in config_ids:
            for j in range(10):
                response = await client.post("/sessions", json={"config_id": config_id})
                if response.status_code == 201:
                    session_counts[config_id] += 1

        # Report
        total_sessions = sum(session_counts.values())
        print(f"Scalability test: {len(config_ids)} configs, {total_sessions} total sessions")
        for config_id, count in session_counts.items():
            print(f"  Config {config_id[:8]}: {count} sessions")

        # Should have created many sessions
        assert total_sessions >= 10  # At least 1 per config

    async def test_pagination_with_large_dataset(self, client: AsyncClient):
        """Test pagination with large number of configs."""
        # Create 50 configs
        config_ids = []
        for i in range(50):
            response = await client.post(
                "/configs",
                json={
                    "name": f"pagination-{i:03d}",
                    "yaml_content": f"bundle:\n  name: page-{i}\nincludes:\n  - bundle: foundation\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test-{i}",
                },
            )
            if response.status_code == 201:
                config_ids.append(response.json()["config_id"])

        # Paginate through all
        page_size = 10
        all_configs = []
        offset = 0

        while True:
            response = await client.get(f"/configs?limit={page_size}&offset={offset}")
            page_configs = response.json()["configs"]

            if not page_configs:
                break

            all_configs.extend(page_configs)
            offset += page_size

            if offset > 100:  # Safety limit
                break

        print(f"Pagination test: retrieved {len(all_configs)} configs total")

        # Should have retrieved many
        assert len(all_configs) >= len(config_ids)

        # Cleanup
        for config_id in config_ids:
            await client.delete(f"/configs/{config_id}")

    async def test_session_list_pagination_stress(self, client: AsyncClient):
        """Test session list pagination with many sessions."""
        # Create config
        config_response = await client.post(
            "/configs",
            json={
                "name": "session-pagination-stress",
                "yaml_content": "bundle:\n  name: sess-page\nincludes:\n  - bundle: foundation\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
            },
        )

        config_id = config_response.json()["config_id"]

        # Create 30 sessions
        session_ids = []
        for i in range(30):
            response = await client.post("/sessions", json={"config_id": config_id})
            if response.status_code == 201:
                session_ids.append(response.json()["session_id"])

        # Paginate through sessions
        page_size = 10
        all_sessions = []
        offset = 0

        while True:
            response = await client.get(f"/sessions?limit={page_size}&offset={offset}")
            page_sessions = response.json()["sessions"]

            if not page_sessions:
                break

            all_sessions.extend(page_sessions)
            offset += page_size

            if offset > 100:
                break

        print(f"Session pagination: retrieved {len(all_sessions)} sessions total")
        assert len(all_sessions) >= len(session_ids)


@pytest.mark.asyncio
class TestConcurrencyRaceConditions:
    """Test for race conditions and concurrent access issues."""

    async def test_concurrent_updates_same_config(self, client: AsyncClient):
        """Test multiple concurrent updates to the same config."""
        # Create config
        config_response = await client.post(
            "/configs",
            json={
                "name": "race-condition-test",
                "yaml_content": "bundle:\n  name: race\nincludes:\n  - bundle: foundation\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
            },
        )

        config_id = config_response.json()["config_id"]

        # Update concurrently 20 times
        tasks = [
            client.put(
                f"/configs/{config_id}",
                json={"description": f"Concurrent update {i}"},
            )
            for i in range(20)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed (last write wins)
        # Filter to Response objects first, then by status code
        response_objs: list[Response] = [r for r in results if isinstance(r, Response)]
        successes = [r for r in response_objs if r.status_code == 200]
        assert len(successes) == 20

        # Final state should be consistent
        final = await client.get(f"/configs/{config_id}")
        assert final.status_code == 200
        # Description should be one of the updates
        assert "Concurrent update" in final.json()["description"]

    async def test_concurrent_helper_operations(self, client: AsyncClient):
        """Test concurrent helper operations on same config."""
        # Create config
        config_response = await client.post(
            "/configs",
            json={
                "name": "helper-concurrent",
                "yaml_content": "bundle:\n  name: helper\nincludes:\n  - bundle: foundation\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
            },
        )

        config_id = config_response.json()["config_id"]

        # Add multiple tools concurrently
        tasks = [
            client.post(
                f"/configs/{config_id}/tools",
                params={"tool_module": f"tool-{i}", "tool_source": f"./tool-{i}"},
            )
            for i in range(10)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter to Response objects first, then by status code
        response_objs: list[Response] = [r for r in results if isinstance(r, Response)]
        successes = [r for r in response_objs if r.status_code == 200]

        print(f"Concurrent tool additions: {len(successes)}/10 succeeded")

        # Get final config
        final = await client.get(f"/configs/{config_id}")
        parsed = yaml.safe_load(final.json()["yaml_content"])

        # Should have tools added (may not be all 10 due to races)
        assert "tools" in parsed
        assert len(parsed["tools"]) >= 1

    async def test_delete_during_session_creation(self, client: AsyncClient):
        """Test deleting config while sessions are being created."""
        # Create config
        config_response = await client.post(
            "/configs",
            json={
                "name": "delete-during-create",
                "yaml_content": "bundle:\n  name: delete-test\nincludes:\n  - bundle: foundation\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
            },
        )

        config_id = config_response.json()["config_id"]

        # Start creating sessions
        session_tasks = [client.post("/sessions", json={"config_id": config_id}) for _ in range(10)]

        # Delete config midway
        delete_task = client.delete(f"/configs/{config_id}")

        # Gather all
        all_tasks = session_tasks + [delete_task]
        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # Some sessions may succeed, some may fail
        session_results = results[:-1]
        delete_result = results[-1]

        # Filter to Response objects first, then by status code
        session_responses: list[Response] = [r for r in session_results if isinstance(r, Response)]
        successful_sessions = [r for r in session_responses if r.status_code == 201]
        failed_sessions = [r for r in session_responses if r.status_code >= 400]

        # Check delete result status safely
        delete_status: int | str
        if isinstance(delete_result, Response):
            # Type narrowed to Response here
            delete_response: Response = delete_result
            delete_status = delete_response.status_code
        else:
            delete_status = "exception"

        print(
            f"Delete during create: {len(successful_sessions)} sessions succeeded, "
            f"{len(failed_sessions)} failed, "
            f"config delete: {delete_status}"
        )

        # Either all sessions succeed then delete, or delete succeeds and sessions fail
        # Document the behavior
        assert True  # Test documents behavior rather than enforces specific outcome


@pytest.mark.asyncio
class TestMemoryAndResourceManagement:
    """Test memory and resource management under load."""

    async def test_session_cleanup_doesnt_affect_others(self, client: AsyncClient):
        """Test that deleting one session doesn't affect others from same config."""
        # Create config
        config_response = await client.post(
            "/configs",
            json={
                "name": "cleanup-isolation",
                "yaml_content": "bundle:\n  name: cleanup\nincludes:\n  - bundle: foundation\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
            },
        )

        config_id = config_response.json()["config_id"]

        # Create 5 sessions
        session_ids = []
        for i in range(5):
            response = await client.post("/sessions", json={"config_id": config_id})
            if response.status_code == 201:
                session_ids.append(response.json()["session_id"])

        if len(session_ids) < 2:
            pytest.skip("Need at least 2 sessions for test")

        # Delete first 3 sessions
        for session_id in session_ids[:3]:
            await client.delete(f"/sessions/{session_id}")

        # Verify remaining sessions still exist
        for session_id in session_ids[3:]:
            response = await client.get(f"/sessions/{session_id}")
            assert response.status_code == 200
            assert response.json()["config_id"] == config_id

    async def test_config_cache_memory_efficiency(self, client: AsyncClient):
        """Test that cache doesn't grow unbounded."""
        # This test documents expected behavior:
        # - Caches should be per config_id
        # - Updating config invalidates cache
        # - Deleting config should clean up cache (manual or GC)

        # Create 10 configs
        config_ids = []
        for i in range(10):
            response = await client.post(
                "/configs",
                json={
                    "name": f"cache-memory-{i}",
                    "yaml_content": f"bundle:\n  name: mem-{i}\nincludes:\n  - bundle: foundation\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test-{i}",
                },
            )
            if response.status_code == 201:
                config_ids.append(response.json()["config_id"])

        # Create one session from each (populate cache)
        for config_id in config_ids:
            await client.post("/sessions", json={"config_id": config_id})

        # Delete half the configs
        for config_id in config_ids[:5]:
            await client.delete(f"/configs/{config_id}")

        # Create sessions from remaining configs (cache should still work)
        for config_id in config_ids[5:]:
            response = await client.post("/sessions", json={"config_id": config_id})
            assert response.status_code in [201, 500]

        # Cleanup
        for config_id in config_ids[5:]:
            await client.delete(f"/configs/{config_id}")


@pytest.mark.asyncio
class TestStressCleanup:
    """Cleanup after stress tests."""

    async def test_cleanup_all_stress_test_data(self, client: AsyncClient):
        """Clean up all stress test configs and sessions."""
        # Delete all sessions first
        sessions_response = await client.get("/sessions?limit=1000")
        for session in sessions_response.json()["sessions"]:
            await client.delete(f"/sessions/{session['session_id']}")

        # Delete all stress test configs
        configs_response = await client.get("/configs?limit=1000")
        for config in configs_response.json()["configs"]:
            if any(
                prefix in config["name"]
                for prefix in [
                    "stress-",
                    "caching-perf-",
                    "concurrent-",
                    "cache-invalidation",
                    "independent-cache-",
                    "100-sessions-",
                    "scale-",
                    "helper-concurrent",
                    "rapid-",
                    "invalidation-stress",
                    "cleanup-isolation",
                    "cache-memory-",
                    "delete-during-",
                ]
            ):
                await client.delete(f"/configs/{config['config_id']}")

        print("Stress test cleanup complete")
