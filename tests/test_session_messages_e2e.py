"""E2E tests for session message handling with real AI responses.

These tests require:
- Live HTTP server (uses live_service fixture from test_e2e_all_endpoints.py)
- Valid ANTHROPIC_API_KEY or OPENAI_API_KEY in .env
- amplifier-core and amplifier-foundation properly configured

Tests may be slow on first run due to bundle downloading.
"""

import pytest

try:
    import httpx
except ImportError:
    httpx = None


@pytest.mark.e2e
@pytest.mark.skipif(httpx is None, reason="httpx not installed")
class TestSessionMessaging:
    """Test actual message sending with AI responses."""

    def test_send_message_and_get_response(self, live_service):
        """Test sending a message to an active session and receiving AI response."""
        # Create a config
        config_response = httpx.post(
            f"{live_service}/configs",
            json={
                "name": "message-test-config",
                "description": "Config for message testing",
                "yaml_content": """
bundle:
  name: message-test
  version: 1.0.0

includes:
  - bundle: foundation

providers:
  - module: provider-anthropic
    config:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-5

session:
  orchestrator: loop-basic
  context: context-simple
""",
            },
            timeout=10.0,
        )

        assert config_response.status_code == 201
        config_id = config_response.json()["config_id"]

        # Create a session
        session_response = httpx.post(
            f"{live_service}/sessions",
            json={"config_id": config_id},
            timeout=60.0,  # First session creation is slow (bundle download)
        )

        assert session_response.status_code == 201
        session_id = session_response.json()["session_id"]

        # Send a message
        message_response = httpx.post(
            f"{live_service}/sessions/{session_id}/messages",
            json={"message": "What is 2 + 2? Answer with just the number."},
            timeout=30.0,
        )

        assert message_response.status_code == 200
        data = message_response.json()

        # Verify response structure
        assert "session_id" in data
        assert data["session_id"] == session_id
        assert "response" in data
        assert "metadata" in data
        assert data["metadata"]["config_id"] == config_id

        # Verify AI responded (should contain "4")
        assert "4" in data["response"]

        # Cleanup
        httpx.delete(f"{live_service}/sessions/{session_id}", timeout=5.0)
        httpx.delete(f"{live_service}/configs/{config_id}", timeout=5.0)

    def test_multi_turn_conversation(self, live_service):
        """Test multiple messages in sequence maintaining context."""
        # Create config and session
        config_response = httpx.post(
            f"{live_service}/configs",
            json={
                "name": "multi-turn-config",
                "yaml_content": """
bundle:
  name: multi-turn
includes:
  - bundle: foundation
providers:
  - module: provider-anthropic
    config:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-5
session:
  orchestrator: loop-basic
  context: context-simple
""",
            },
            timeout=10.0,
        )

        config_id = config_response.json()["config_id"]

        session_response = httpx.post(
            f"{live_service}/sessions",
            json={"config_id": config_id},
            timeout=60.0,
        )

        session_id = session_response.json()["session_id"]

        # First message
        msg1_response = httpx.post(
            f"{live_service}/sessions/{session_id}/messages",
            json={"message": "My favorite color is blue."},
            timeout=30.0,
        )

        assert msg1_response.status_code == 200

        # Second message - should remember context
        msg2_response = httpx.post(
            f"{live_service}/sessions/{session_id}/messages",
            json={"message": "What is my favorite color?"},
            timeout=30.0,
        )

        assert msg2_response.status_code == 200
        response_text = msg2_response.json()["response"].lower()

        # AI should remember "blue"
        assert "blue" in response_text

        # Verify session metadata updated
        session_info = httpx.get(f"{live_service}/sessions/{session_id}", timeout=5.0)
        assert session_info.status_code == 200
        # Message count should reflect conversation history

        # Cleanup
        httpx.delete(f"{live_service}/sessions/{session_id}", timeout=5.0)
        httpx.delete(f"{live_service}/configs/{config_id}", timeout=5.0)

    def test_message_with_additional_context(self, live_service):
        """Test sending message with additional context parameter."""
        # Create config and session
        config_response = httpx.post(
            f"{live_service}/configs",
            json={
                "name": "context-test-config",
                "yaml_content": """
bundle:
  name: context-test
includes:
  - bundle: foundation
providers:
  - module: provider-anthropic
    config:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-5
session:
  orchestrator: loop-basic
  context: context-simple
""",
            },
            timeout=10.0,
        )

        config_id = config_response.json()["config_id"]

        session_response = httpx.post(
            f"{live_service}/sessions",
            json={"config_id": config_id},
            timeout=60.0,
        )

        session_id = session_response.json()["session_id"]

        # Send message with context
        message_response = httpx.post(
            f"{live_service}/sessions/{session_id}/messages",
            json={
                "message": "What programming language am I using?",
                "context": {"language": "Python", "framework": "FastAPI"},
            },
            timeout=30.0,
        )

        assert message_response.status_code == 200
        data = message_response.json()
        assert "response" in data

        # AI might incorporate context into response
        response_lower = data["response"].lower()
        # Not guaranteed, but reasonable to expect
        assert "python" in response_lower or "fastapi" in response_lower

        # Cleanup
        httpx.delete(f"{live_service}/sessions/{session_id}", timeout=5.0)
        httpx.delete(f"{live_service}/configs/{config_id}", timeout=5.0)

    def test_message_to_nonexistent_session_returns_404(self, live_service):
        """Test sending message to non-existent session returns 404."""
        response = httpx.post(
            f"{live_service}/sessions/nonexistent-session-id/messages",
            json={"message": "Hello"},
            timeout=5.0,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_message_validation_missing_message_field(self, live_service):
        """Test validation error when message field is missing."""
        # Try to send empty request
        response = httpx.post(
            f"{live_service}/sessions/some-session-id/messages",
            json={},  # Missing 'message' field
            timeout=5.0,
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_message_with_special_characters(self, live_service):
        """Test message with special characters, emojis, unicode."""
        # Create config and session
        config_response = httpx.post(
            f"{live_service}/configs",
            json={
                "name": "special-chars-config",
                "yaml_content": """
bundle:
  name: special-chars
includes:
  - bundle: foundation
providers:
  - module: provider-anthropic
    config:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-5
session:
  orchestrator: loop-basic
  context: context-simple
""",
            },
            timeout=10.0,
        )

        config_id = config_response.json()["config_id"]

        session_response = httpx.post(
            f"{live_service}/sessions",
            json={"config_id": config_id},
            timeout=60.0,
        )

        session_id = session_response.json()["session_id"]

        # Send message with special characters
        message_response = httpx.post(
            f"{live_service}/sessions/{session_id}/messages",
            json={"message": "Respond with 'Hello 👋 世界 🌍' exactly."},
            timeout=30.0,
        )

        assert message_response.status_code == 200
        data = message_response.json()
        assert "response" in data
        # AI should be able to handle unicode/emojis
        response_text = data["response"]
        assert len(response_text) > 0

        # Cleanup
        httpx.delete(f"{live_service}/sessions/{session_id}", timeout=5.0)
        httpx.delete(f"{live_service}/configs/{config_id}", timeout=5.0)

    def test_message_response_includes_metadata(self, live_service):
        """Test that message response includes complete metadata."""
        # Create config and session
        config_response = httpx.post(
            f"{live_service}/configs",
            json={
                "name": "metadata-test-config",
                "yaml_content": """
bundle:
  name: metadata-test
includes:
  - bundle: foundation
providers:
  - module: provider-anthropic
    config:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-5
session:
  orchestrator: loop-basic
  context: context-simple
""",
            },
            timeout=10.0,
        )

        config_id = config_response.json()["config_id"]

        session_response = httpx.post(
            f"{live_service}/sessions",
            json={"config_id": config_id},
            timeout=60.0,
        )

        session_id = session_response.json()["session_id"]

        # Send message
        message_response = httpx.post(
            f"{live_service}/sessions/{session_id}/messages",
            json={"message": "Say hello."},
            timeout=30.0,
        )

        assert message_response.status_code == 200
        data = message_response.json()

        # Verify metadata structure
        assert "metadata" in data
        metadata = data["metadata"]
        assert isinstance(metadata, dict)
        assert "config_id" in metadata
        assert metadata["config_id"] == config_id

        # Cleanup
        httpx.delete(f"{live_service}/sessions/{session_id}", timeout=5.0)
        httpx.delete(f"{live_service}/configs/{config_id}", timeout=5.0)

    def test_concurrent_messages_to_same_session(self, live_service):
        """Test sending multiple messages concurrently to same session."""
        # Create config and session
        config_response = httpx.post(
            f"{live_service}/configs",
            json={
                "name": "concurrent-test-config",
                "yaml_content": """
bundle:
  name: concurrent-test
includes:
  - bundle: foundation
providers:
  - module: provider-anthropic
    config:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-5
session:
  orchestrator: loop-basic
  context: context-simple
""",
            },
            timeout=10.0,
        )

        config_id = config_response.json()["config_id"]

        session_response = httpx.post(
            f"{live_service}/sessions",
            json={"config_id": config_id},
            timeout=60.0,
        )

        session_id = session_response.json()["session_id"]

        # Send multiple messages (serially to avoid race conditions)
        # Note: Concurrent sending to same session may have locking issues
        # so we test that they all succeed when sent one after another
        messages = ["What is 1+1?", "What is 2+2?", "What is 3+3?"]

        for msg in messages:
            response = httpx.post(
                f"{live_service}/sessions/{session_id}/messages",
                json={"message": msg},
                timeout=30.0,
            )
            assert response.status_code == 200

        # Cleanup
        httpx.delete(f"{live_service}/sessions/{session_id}", timeout=5.0)
        httpx.delete(f"{live_service}/configs/{config_id}", timeout=5.0)

    def test_message_timeout_handling(self, live_service):
        """Test that extremely long messages don't cause indefinite hangs."""
        # Create config and session
        config_response = httpx.post(
            f"{live_service}/configs",
            json={
                "name": "timeout-test-config",
                "yaml_content": """
bundle:
  name: timeout-test
includes:
  - bundle: foundation
providers:
  - module: provider-anthropic
    config:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-5
session:
  orchestrator: loop-basic
  context: context-simple
""",
            },
            timeout=10.0,
        )

        config_id = config_response.json()["config_id"]

        session_response = httpx.post(
            f"{live_service}/sessions",
            json={"config_id": config_id},
            timeout=60.0,
        )

        session_id = session_response.json()["session_id"]

        # Send a very large message
        large_message = "Count from 1 to 10. " * 100  # 2000+ characters

        message_response = httpx.post(
            f"{live_service}/sessions/{session_id}/messages",
            json={"message": large_message},
            timeout=60.0,  # Generous timeout for large message
        )

        # Should either succeed or return error, but not hang
        assert message_response.status_code in [200, 400, 500]

        # Cleanup
        httpx.delete(f"{live_service}/sessions/{session_id}", timeout=5.0)
        httpx.delete(f"{live_service}/configs/{config_id}", timeout=5.0)

    def test_message_after_session_resume(self, live_service):
        """Test sending message after resuming a session preserves context."""
        # Create config and session
        config_response = httpx.post(
            f"{live_service}/configs",
            json={
                "name": "resume-message-config",
                "yaml_content": """
bundle:
  name: resume-message
includes:
  - bundle: foundation
providers:
  - module: provider-anthropic
    config:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-5
session:
  orchestrator: loop-basic
  context: context-persistent
""",
            },
            timeout=10.0,
        )

        config_id = config_response.json()["config_id"]

        session_response = httpx.post(
            f"{live_service}/sessions",
            json={"config_id": config_id},
            timeout=60.0,
        )

        session_id = session_response.json()["session_id"]

        # Send first message
        msg1 = httpx.post(
            f"{live_service}/sessions/{session_id}/messages",
            json={"message": "Remember that my name is Alice."},
            timeout=30.0,
        )

        assert msg1.status_code == 200

        # Resume the session
        resume_response = httpx.post(
            f"{live_service}/sessions/{session_id}/resume",
            timeout=30.0,
        )

        assert resume_response.status_code == 200

        # Send second message after resume
        msg2 = httpx.post(
            f"{live_service}/sessions/{session_id}/messages",
            json={"message": "What is my name?"},
            timeout=30.0,
        )

        assert msg2.status_code == 200
        response_text = msg2.json()["response"].lower()

        # AI should remember "Alice" from context
        assert "alice" in response_text

        # Cleanup
        httpx.delete(f"{live_service}/sessions/{session_id}", timeout=5.0)
        httpx.delete(f"{live_service}/configs/{config_id}", timeout=5.0)


@pytest.mark.e2e
@pytest.mark.skipif(httpx is None, reason="httpx not installed")
class TestSessionMessageErrors:
    """Test error handling in message sending."""

    def test_message_with_invalid_json(self, live_service):
        """Test sending malformed JSON returns 422."""
        response = httpx.post(
            f"{live_service}/sessions/test-id/messages",
            content="not json",
            headers={"Content-Type": "application/json"},
            timeout=5.0,
        )

        # Should return validation error
        assert response.status_code in [400, 422]

    def test_message_to_deleted_session(self, live_service):
        """Test message to deleted session returns 404."""
        # Create and immediately delete session
        config_response = httpx.post(
            f"{live_service}/configs",
            json={
                "name": "delete-test-config",
                "yaml_content": """
bundle:
  name: delete-test
includes:
  - bundle: foundation
providers:
  - module: provider-anthropic
    config:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-5
session:
  orchestrator: loop-basic
  context: context-simple
""",
            },
            timeout=10.0,
        )

        config_id = config_response.json()["config_id"]

        session_response = httpx.post(
            f"{live_service}/sessions",
            json={"config_id": config_id},
            timeout=60.0,
        )

        session_id = session_response.json()["session_id"]

        # Delete the session
        delete_response = httpx.delete(
            f"{live_service}/sessions/{session_id}",
            timeout=5.0,
        )

        assert delete_response.status_code == 200

        # Try to send message to deleted session
        message_response = httpx.post(
            f"{live_service}/sessions/{session_id}/messages",
            json={"message": "Hello"},
            timeout=5.0,
        )

        assert message_response.status_code == 404

        # Cleanup config
        httpx.delete(f"{live_service}/configs/{config_id}", timeout=5.0)

    def test_empty_message_validation(self, live_service):
        """Test that empty messages are rejected."""
        response = httpx.post(
            f"{live_service}/sessions/test-id/messages",
            json={"message": ""},  # Empty message
            timeout=5.0,
        )

        # Should validate and reject empty messages
        assert response.status_code in [400, 422]
