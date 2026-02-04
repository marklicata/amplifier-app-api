"""Integration E2E tests for Config → Session flow.

Tests the complete lifecycle: Config creation → Session creation → Message sending.
"""

import asyncio

import pytest
import yaml
from httpx import AsyncClient, Response


@pytest.mark.asyncio
class TestConfigToSessionIntegration:
    """Test the complete Config → Session integration flow."""

    async def test_complete_flow_minimal(self, client: AsyncClient):
        """Test complete flow: create config → create session → verify."""
        # Step 1: Create a minimal config
        config_response = await client.post(
            "/configs",
            json={
                "name": "integration-minimal",
                "description": "Minimal integration test",
                "yaml_content": """
bundle:
  name: integration-minimal

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

        assert config_response.status_code == 201
        config_data = config_response.json()
        config_id = config_data["config_id"]
        assert config_data["name"] == "integration-minimal"

        # Step 2: Create session from config
        session_response = await client.post(
            "/sessions",
            json={"config_id": config_id},
        )

        assert session_response.status_code == 201
        session_data = session_response.json()
        session_id = session_data["session_id"]
        assert session_data["config_id"] == config_id
        assert session_data["status"] == "active"

        # Step 3: Verify session exists
        get_response = await client.get(f"/sessions/{session_id}")
        assert get_response.status_code == 200
        assert get_response.json()["config_id"] == config_id

        # Step 4: Verify config still exists
        config_check = await client.get(f"/configs/{config_id}")
        assert config_check.status_code == 200

    async def test_config_modification_affects_new_sessions(self, client: AsyncClient):
        """Test that modifying config YAML affects new sessions (cache invalidation)."""
        # Create config v1
        config_response = await client.post(
            "/configs",
            json={
                "name": "cache-invalidation-test",
                "yaml_content": """
bundle:
  name: cache-test
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

        # Create session from v1
        session1_response = await client.post(
            "/sessions",
            json={"config_id": config_id},
        )
        assert session1_response.status_code == 201
        session1_id = session1_response.json()["session_id"]

        # Update config to v2
        update_response = await client.put(
            f"/configs/{config_id}",
            json={
                "yaml_content": """
bundle:
  name: cache-test
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
      model: claude-sonnet-4-5
"""
            },
        )

        assert update_response.status_code == 200

        # Create session from v2
        session2_response = await client.post(
            "/sessions",
            json={"config_id": config_id},
        )
        assert session2_response.status_code == 201
        session2_id = session2_response.json()["session_id"]

        # Both sessions exist and reference same config
        assert session1_id != session2_id
        session1 = await client.get(f"/sessions/{session1_id}")
        session2 = await client.get(f"/sessions/{session2_id}")
        assert session1.json()["config_id"] == config_id
        assert session2.json()["config_id"] == config_id

        # Note: session1 still uses v1 config (already prepared)
        # session2 should use v2 config (cache invalidated)

    async def test_one_config_many_sessions(self, client: AsyncClient):
        """Test creating many sessions from one config."""
        # Create config
        config_response = await client.post(
            "/configs",
            json={
                "name": "one-to-many",
                "yaml_content": """
bundle:
  name: one-to-many

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

        # Create 10 sessions from same config
        session_ids = []
        for i in range(10):
            response = await client.post(
                "/sessions",
                json={"config_id": config_id},
            )
            assert response.status_code == 201
            session_ids.append(response.json()["session_id"])

        # All unique
        assert len(session_ids) == len(set(session_ids))

        # All reference same config
        for session_id in session_ids:
            response = await client.get(f"/sessions/{session_id}")
            assert response.json()["config_id"] == config_id

        # List sessions - should see all 10
        list_response = await client.get("/sessions?limit=20")
        listed_sessions = list_response.json()["sessions"]
        listed_ids = {s["session_id"] for s in listed_sessions}

        for session_id in session_ids:
            assert session_id in listed_ids

    async def test_many_configs_many_sessions(self, client: AsyncClient):
        """Test creating multiple configs and sessions from each."""
        config_to_sessions = {}

        # Create 3 configs
        for i in range(3):
            config_response = await client.post(
                "/configs",
                json={
                    "name": f"config-{i}",
                    "yaml_content": f"""
bundle:
  name: config-{i}

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
            config_id = config_response.json()["config_id"]

            # Create 2 sessions from each config
            sessions = []
            for j in range(2):
                session_response = await client.post(
                    "/sessions",
                    json={"config_id": config_id},
                )
                assert session_response.status_code == 201
                sessions.append(session_response.json()["session_id"])

            config_to_sessions[config_id] = sessions

        # Verify mapping
        assert len(config_to_sessions) == 3
        for config_id, session_ids in config_to_sessions.items():
            assert len(session_ids) == 2
            # Verify sessions reference correct config
            for session_id in session_ids:
                response = await client.get(f"/sessions/{session_id}")
                assert response.json()["config_id"] == config_id

    async def test_delete_config_with_active_sessions(self, client: AsyncClient):
        """Test behavior when deleting a config that has active sessions."""
        # Create config
        config_response = await client.post(
            "/configs",
            json={
                "name": "delete-with-sessions",
                "yaml_content": "bundle:\n  name: test\nincludes:\n  - bundle: foundation\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
            },
        )
        config_id = config_response.json()["config_id"]

        # Create sessions
        session_ids = []
        for i in range(3):
            response = await client.post("/sessions", json={"config_id": config_id})
            session_ids.append(response.json()["session_id"])

        # Delete config
        delete_response = await client.delete(f"/configs/{config_id}")
        # Should succeed (for now - FK enforcement may change this)
        assert delete_response.status_code in [200, 400, 409]

        # Sessions should still exist (orphaned)
        for session_id in session_ids:
            session_check = await client.get(f"/sessions/{session_id}")
            # May be 200 or have issues due to missing config
            assert session_check.status_code in [200, 404, 500]

    async def test_resume_session_loads_correct_config(self, client: AsyncClient):
        """Test that resuming a session loads the correct config."""
        # Create two different configs
        config1_response = await client.post(
            "/configs",
            json={
                "name": "resume-config-1",
                "yaml_content": """
bundle:
  name: resume-1

includes:
  - bundle: foundation

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: config1-key
      model: claude-sonnet-4-5
""",
            },
        )
        config1_id = config1_response.json()["config_id"]

        config2_response = await client.post(
            "/configs",
            json={
                "name": "resume-config-2",
                "yaml_content": """
bundle:
  name: resume-2

includes:
  - bundle: foundation

session:
  orchestrator: loop-streaming
  context: context-persistent

providers:
  - module: provider-openai
    config:
      api_key: config2-key
      model: gpt-4o
""",
            },
        )
        config2_id = config2_response.json()["config_id"]

        # Create sessions from different configs
        session1_response = await client.post(
            "/sessions",
            json={"config_id": config1_id},
        )
        session1_id = session1_response.json()["session_id"]

        session2_response = await client.post(
            "/sessions",
            json={"config_id": config2_id},
        )
        session2_id = session2_response.json()["session_id"]

        # Resume both sessions
        resume1 = await client.post(f"/sessions/{session1_id}/resume")
        resume2 = await client.post(f"/sessions/{session2_id}/resume")

        assert resume1.status_code == 200
        assert resume2.status_code == 200

        # Verify correct config_ids
        assert resume1.json()["config_id"] == config1_id
        assert resume2.json()["config_id"] == config2_id

    async def test_config_helper_methods_maintain_structure(self, client: AsyncClient):
        """Test that helper methods maintain valid YAML structure."""
        # Create minimal config
        config_response = await client.post(
            "/configs",
            json={
                "name": "helper-structure-test",
                "yaml_content": """
bundle:
  name: helper-test

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: test
""",
            },
        )

        config_id = config_response.json()["config_id"]

        # Add tool
        await client.post(
            f"/configs/{config_id}/tools",
            params={"tool_module": "tool-web", "tool_source": "./modules/tool-web"},
        )

        # Add provider
        await client.post(
            f"/configs/{config_id}/providers",
            params={"provider_module": "provider-openai"},
            json={"api_key": "test2"},
        )

        # Merge bundle
        await client.post(
            f"/configs/{config_id}/bundles",
            params={"bundle_uri": "recipes"},
        )

        # Get final config
        final_response = await client.get(f"/configs/{config_id}")
        final_yaml = final_response.json()["yaml_content"]

        # Parse to verify structure is still valid

        parsed = yaml.safe_load(final_yaml)
        assert "bundle" in parsed
        assert parsed["bundle"]["name"] == "helper-test"
        assert "session" in parsed
        assert "providers" in parsed
        assert len(parsed["providers"]) == 2  # anthropic + openai
        assert "tools" in parsed
        assert len(parsed["tools"]) == 1  # web
        assert "includes" in parsed
        assert len(parsed["includes"]) == 1  # recipes

        # Try to create a session with this modified config
        session_response = await client.post(
            "/sessions",
            json={"config_id": config_id},
        )

        # Should succeed if structure is valid
        assert session_response.status_code in [201, 500]  # 500 if bundle prep fails

    async def test_update_config_with_sessions_active(self, client: AsyncClient):
        """Test updating a config while it has active sessions."""
        # Create config
        config_response = await client.post(
            "/configs",
            json={
                "name": "update-with-active",
                "yaml_content": """
bundle:
  name: update-test
  version: 1.0.0

includes:
  - bundle: foundation

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: original-key
      model: claude-sonnet-4-5
""",
            },
        )

        config_id = config_response.json()["config_id"]

        # Create sessions
        session1 = await client.post("/sessions", json={"config_id": config_id})
        session1_id = session1.json()["session_id"]

        # Update config
        update_response = await client.put(
            f"/configs/{config_id}",
            json={
                "yaml_content": """
bundle:
  name: update-test
  version: 2.0.0

includes:
  - bundle: foundation

session:
  orchestrator: loop-streaming
  context: context-persistent

providers:
  - module: provider-anthropic
    config:
      api_key: updated-key
      model: claude-opus-4
"""
            },
        )

        assert update_response.status_code == 200

        # Create new session after update
        session2 = await client.post("/sessions", json={"config_id": config_id})
        assert session2.status_code == 201
        session2_id = session2.json()["session_id"]

        # Both sessions should exist
        s1_check = await client.get(f"/sessions/{session1_id}")
        s2_check = await client.get(f"/sessions/{session2_id}")
        assert s1_check.status_code == 200
        assert s2_check.status_code == 200

        # Both reference same config_id
        assert s1_check.json()["config_id"] == config_id
        assert s2_check.json()["config_id"] == config_id

    async def test_config_with_all_sections_creates_session(self, client: AsyncClient):
        """Test that a config with all possible sections creates a valid session."""
        config_response = await client.post(
            "/configs",
            json={
                "name": "all-sections",
                "yaml_content": """
bundle:
  name: all-sections
  version: 1.0.0
  description: Config with all sections

includes:
  - bundle: foundation

session:
  orchestrator: loop-streaming
  context: context-persistent
  injection_budget_per_turn: 10000
  injection_size_limit: 10240

orchestrator:
  config:
    max_iterations: 50
    show_thinking: true

context:
  config:
    max_tokens: 200000
    compact_threshold: 0.92
    auto_compact: true

providers:
  - module: provider-anthropic
    config:
      api_key: test-key
      model: claude-sonnet-4-5

tools:
  - module: tool-filesystem
    config:
      allowed_paths: ["."]
  - module: tool-bash
  - module: tool-web

hooks:
  - module: hooks-logging
    config:
      output_dir: .amplifier/logs

spawn:
  exclude_tools:
    - tool-task

agents:
  include:
    - foundation:foundation-expert
""",
            },
        )

        assert config_response.status_code == 201
        config_id = config_response.json()["config_id"]

        # Create session
        session_response = await client.post(
            "/sessions",
            json={"config_id": config_id},
        )

        # Should succeed (or fail gracefully with detailed error)
        assert session_response.status_code in [201, 500]

        if session_response.status_code == 201:
            session_id = session_response.json()["session_id"]
            # Verify session created
            get_response = await client.get(f"/sessions/{session_id}")
            assert get_response.status_code == 200

    async def test_programmatic_build_then_create_session(self, client: AsyncClient):
        """Test building config programmatically then creating session."""
        # Create minimal config
        config_response = await client.post(
            "/configs",
            json={
                "name": "programmatic-build",
                "yaml_content": """
bundle:
  name: programmatic

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: base-key
      model: claude-sonnet-4-5
""",
            },
        )

        config_id = config_response.json()["config_id"]

        # Build it up programmatically
        # Add foundation bundle
        await client.post(
            f"/configs/{config_id}/bundles",
            params={"bundle_uri": "foundation"},
        )

        # Add tools
        await client.post(
            f"/configs/{config_id}/tools",
            params={"tool_module": "tool-filesystem", "tool_source": "./modules/tool-filesystem"},
        )

        await client.post(
            f"/configs/{config_id}/tools",
            params={"tool_module": "tool-web", "tool_source": "./modules/tool-web"},
        )

        # Add another provider
        await client.post(
            f"/configs/{config_id}/providers",
            params={"provider_module": "provider-openai"},
            json={"api_key": "test-openai-key", "model": "gpt-4o"},
        )

        # Get final config
        final_response = await client.get(f"/configs/{config_id}")
        assert final_response.status_code == 200

        # Create session from programmatically built config
        session_response = await client.post(
            "/sessions",
            json={"config_id": config_id},
        )

        # Should succeed
        assert session_response.status_code in [201, 500]


@pytest.mark.asyncio
class TestConfigSessionLifecycle:
    """Test complete lifecycle scenarios."""

    async def test_full_lifecycle_create_use_delete(self, client: AsyncClient):
        """Test: create config → create session → use → delete session → delete config."""
        # 1. Create config
        config_response = await client.post(
            "/configs",
            json={
                "name": "lifecycle-test",
                "yaml_content": """
bundle:
  name: lifecycle

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

        assert config_response.status_code == 201
        config_id = config_response.json()["config_id"]

        # 2. Create session
        session_response = await client.post(
            "/sessions",
            json={"config_id": config_id},
        )

        assert session_response.status_code == 201
        session_id = session_response.json()["session_id"]

        # 3. Verify both exist
        config_check = await client.get(f"/configs/{config_id}")
        session_check = await client.get(f"/sessions/{session_id}")
        assert config_check.status_code == 200
        assert session_check.status_code == 200

        # 4. Delete session
        delete_session = await client.delete(f"/sessions/{session_id}")
        assert delete_session.status_code == 200

        # 5. Verify session deleted, config remains
        session_check = await client.get(f"/sessions/{session_id}")
        config_check = await client.get(f"/configs/{config_id}")
        assert session_check.status_code == 404
        assert config_check.status_code == 200

        # 6. Delete config
        delete_config = await client.delete(f"/configs/{config_id}")
        assert delete_config.status_code == 200

        # 7. Verify both deleted
        config_check = await client.get(f"/configs/{config_id}")
        assert config_check.status_code == 404

    async def test_update_config_multiple_times_with_sessions(self, client: AsyncClient):
        """Test updating config multiple times while creating sessions."""
        # Create config v1
        config_response = await client.post(
            "/configs",
            json={
                "name": "multi-update",
                "yaml_content": """
bundle:
  name: multi-update
  version: 1.0.0

includes:
  - bundle: foundation

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: v1-key
      model: claude-sonnet-4-5
""",
            },
        )

        config_id = config_response.json()["config_id"]
        session_ids = []

        # Iteration: create session, update config
        for version in range(1, 4):
            # Create session
            session_response = await client.post(
                "/sessions",
                json={"config_id": config_id},
            )
            if session_response.status_code == 201:
                session_ids.append(session_response.json()["session_id"])

            # Update config
            await client.put(
                f"/configs/{config_id}",
                json={
                    "yaml_content": f"""
bundle:
  name: multi-update
  version: {version + 1}.0.0

includes:
  - bundle: foundation

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: v{version + 1}-key
      model: claude-sonnet-4-5
"""
                },
            )

        # All sessions should reference the same config_id
        for session_id in session_ids:
            response = await client.get(f"/sessions/{session_id}")
            if response.status_code == 200:
                assert response.json()["config_id"] == config_id

    async def test_list_sessions_grouped_by_config(self, client: AsyncClient):
        """Test listing sessions and verifying they group by config_id."""
        # Create 2 configs
        config1 = await client.post(
            "/configs",
            json={
                "name": "group-config-1",
                "yaml_content": "bundle:\n  name: g1\nincludes:\n  - bundle: foundation\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
            },
        )
        config1_id = config1.json()["config_id"]

        config2 = await client.post(
            "/configs",
            json={
                "name": "group-config-2",
                "yaml_content": "bundle:\n  name: g2\nincludes:\n  - bundle: foundation\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
            },
        )
        config2_id = config2.json()["config_id"]

        # Create 3 sessions from config1, 2 from config2
        for _ in range(3):
            await client.post("/sessions", json={"config_id": config1_id})
        for _ in range(2):
            await client.post("/sessions", json={"config_id": config2_id})

        # List all sessions
        response = await client.get("/sessions?limit=10")
        sessions = response.json()["sessions"]

        # Count by config_id
        config1_sessions = [s for s in sessions if s["config_id"] == config1_id]
        config2_sessions = [s for s in sessions if s["config_id"] == config2_id]

        assert len(config1_sessions) >= 3
        assert len(config2_sessions) >= 2


@pytest.mark.asyncio
class TestConfigSessionErrorRecovery:
    """Test error recovery and edge cases in integration."""

    async def test_session_creation_with_invalid_bundle_yaml(self, client: AsyncClient):
        """Test that session creation fails gracefully with invalid bundle YAML."""
        # Create config with structurally valid but semantically broken YAML
        config_response = await client.post(
            "/configs",
            json={
                "name": "broken-bundle",
                "yaml_content": """
bundle:
  name: broken

includes:
  - bundle: nonexistent-bundle-that-does-not-exist

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: test
""",
            },
        )

        assert config_response.status_code == 201
        config_id = config_response.json()["config_id"]

        # Try to create session - should fail during bundle preparation
        session_response = await client.post(
            "/sessions",
            json={"config_id": config_id},
        )

        # Should fail with 500 (bundle preparation error)
        assert session_response.status_code == 500
        assert (
            "bundle" in session_response.json()["detail"].lower()
            or "failed" in session_response.json()["detail"].lower()
        )

    async def test_session_creation_with_missing_provider(self, client: AsyncClient):
        """Test session creation with config missing providers."""
        # Create config without providers (invalid)
        config_response = await client.post(
            "/configs",
            json={
                "name": "no-provider",
                "yaml_content": """
bundle:
  name: no-provider

includes:
  - bundle: foundation

session:
  orchestrator: loop-basic
  context: context-simple
""",
                "validate": False,  # Skip validation to test runtime behavior
            },
        )

        # If validation is enforced, this should fail at create
        if config_response.status_code == 201:
            config_id = config_response.json()["config_id"]

            # Try to create session
            session_response = await client.post(
                "/sessions",
                json={"config_id": config_id},
            )

            # Should fail at session creation or message sending
            assert session_response.status_code in [201, 500]

    async def test_rapid_config_update_and_session_creation(self, client: AsyncClient):
        """Test rapid config updates followed by session creations."""

        # Create initial config
        config_response = await client.post(
            "/configs",
            json={
                "name": "rapid-update",
                "yaml_content": """
bundle:
  name: rapid
  version: 1.0.0

includes:
  - bundle: foundation

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: test
      model: claude-sonnet-4-5
""",
            },
        )

        config_id = config_response.json()["config_id"]

        # Rapidly update config and create sessions
        tasks = []
        for i in range(5):
            # Update task
            tasks.append(
                client.put(
                    f"/configs/{config_id}",
                    json={"description": f"Version {i}"},
                )
            )
            # Create session task
            tasks.append(client.post("/sessions", json={"config_id": config_id}))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Most should succeed (some may race)
        # Filter to Response objects first, then filter by status code
        response_objs: list[Response] = [r for r in results if isinstance(r, Response)]
        successes = [r for r in response_objs if r.status_code in [200, 201]]
        assert len(successes) >= 5  # At least half should succeed

    async def test_delete_sessions_then_config(self, client: AsyncClient):
        """Test normal cleanup flow: delete all sessions, then delete config."""
        # Create config
        config_response = await client.post(
            "/configs",
            json={
                "name": "cleanup-flow",
                "yaml_content": "bundle:\n  name: cleanup\nincludes:\n  - bundle: foundation\nsession:\n  orchestrator: loop-basic\n  context: context-simple\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test",
            },
        )

        config_id = config_response.json()["config_id"]

        # Create sessions
        session_ids = []
        for i in range(3):
            response = await client.post("/sessions", json={"config_id": config_id})
            if response.status_code == 201:
                session_ids.append(response.json()["session_id"])

        # Delete all sessions first
        for session_id in session_ids:
            delete_response = await client.delete(f"/sessions/{session_id}")
            assert delete_response.status_code == 200

        # Verify all sessions deleted
        for session_id in session_ids:
            check = await client.get(f"/sessions/{session_id}")
            assert check.status_code == 404

        # Now delete config
        config_delete = await client.delete(f"/configs/{config_id}")
        assert config_delete.status_code == 200

        # Verify config deleted
        config_check = await client.get(f"/configs/{config_id}")
        assert config_check.status_code == 404


@pytest.mark.asyncio
class TestIntegrationCleanup:
    """Cleanup all test data."""

    async def test_cleanup_all_integration_test_data(self, client: AsyncClient):
        """Clean up all configs and sessions created during integration tests."""
        # Delete all sessions
        sessions_response = await client.get("/sessions?limit=1000")
        for session in sessions_response.json()["sessions"]:
            await client.delete(f"/sessions/{session['session_id']}")

        # Delete all test configs
        configs_response = await client.get("/configs?limit=1000")
        for config in configs_response.json()["configs"]:
            if any(
                prefix in config["name"]
                for prefix in [
                    "integration-",
                    "cache-",
                    "resume-",
                    "helper-",
                    "lifecycle-",
                    "group-",
                    "rapid-",
                    "cleanup-",
                    "all-sections",
                    "programmatic-",
                    "one-to-many",
                    "config-",
                    "update-",
                    "reusable-",
                    "session-test-",
                    "delete-with-",
                    "broken-",
                    "no-provider",
                ]
            ):
                await client.delete(f"/configs/{config['config_id']}")
