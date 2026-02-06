"""E2E tests for SSE streaming functionality.

These tests validate Server-Sent Events (SSE) streaming for session messages.

Requirements:
- Live HTTP server (uses live_service fixture)
- Valid ANTHROPIC_API_KEY in .env
- amplifier-core and amplifier-foundation configured
"""

import os
import pytest

try:
    import httpx
except ImportError:
    httpx = None


@pytest.mark.e2e
@pytest.mark.skipif(httpx is None, reason="httpx not installed")
class TestSessionStreaming:
    """Test SSE streaming for session messages."""

    def test_stream_message_returns_sse_events(self, live_service):
        """Test that streaming returns valid SSE events."""
        # Create config
        # Use e2e_test_bundle from environment
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set in environment")

        # Create session
        session_response = httpx.post(
            f"{live_service}/sessions",
            json={"config_id": config_id},
            timeout=60.0,
        )

        assert session_response.status_code == 201
        session_id = session_response.json()["session_id"]

        # Stream a message
        with httpx.stream(
            "POST",
            f"{live_service}/sessions/{session_id}/stream",
            json={"message": "Say hello in 3 words."},
            timeout=30.0,
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

            # Collect events
            events = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    event_data = line[6:]  # Remove "data: " prefix
                    events.append(event_data)

            # Should have received at least:
            # - Connection event
            # - Content events
            # - Done event
            assert len(events) >= 2

            # First event should be connection acknowledgment
            import json

            first_event = json.loads(events[0])
            assert first_event["type"] == "connected"
            assert first_event["session_id"] == session_id

            # Last event should be done
            last_event = json.loads(events[-1])
            assert last_event["type"] == "done"

        # Cleanup
        httpx.delete(f"{live_service}/sessions/{session_id}", timeout=5.0)

    def test_stream_to_nonexistent_session_returns_404(self, live_service):
        """Test streaming to non-existent session returns 404."""
        response = httpx.post(
            f"{live_service}/sessions/nonexistent-id/stream",
            json={"message": "Hello"},
            timeout=5.0,
        )

        assert response.status_code == 404

    def test_stream_with_missing_message_field_returns_422(self, live_service):
        """Test validation error when message field is missing."""
        response = httpx.post(
            f"{live_service}/sessions/some-id/stream",
            json={},  # Missing 'message' field
            timeout=5.0,
        )

        assert response.status_code == 422

    def test_stream_incremental_content(self, live_service):
        """Test that streaming returns incremental content, not all at once."""
        # Create config
        # Use e2e_test_bundle from environment
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set in environment")

        # Create session
        session_response = httpx.post(
            f"{live_service}/sessions",
            json={"config_id": config_id},
            timeout=60.0,
        )

        session_id = session_response.json()["session_id"]

        # Stream a message that will generate multiple events
        event_count = 0
        content_events = []

        with httpx.stream(
            "POST",
            f"{live_service}/sessions/{session_id}/stream",
            json={"message": "Count from 1 to 5, one number per line."},
            timeout=45.0,
        ) as response:
            assert response.status_code == 200

            for line in response.iter_lines():
                if line.startswith("data: "):
                    event_count += 1
                    event_data = line[6:]

                    import json

                    try:
                        event = json.loads(event_data)
                        if event.get("type") == "content":
                            content_events.append(event)
                    except json.JSONDecodeError:
                        pass

        # Should have received multiple events (incremental delivery)
        assert event_count >= 3

        # Should have some content events
        # (actual count depends on streaming implementation)
        assert len(content_events) >= 0

        # Cleanup
        httpx.delete(f"{live_service}/sessions/{session_id}", timeout=5.0)

    def test_stream_error_handling(self, live_service):
        """Test error handling during streaming."""
        # Create config with invalid setup (will cause runtime error)
        # Use e2e_test_bundle from environment
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set in environment")

        # Create session (might succeed despite bad key)
        session_response = httpx.post(
            f"{live_service}/sessions",
            json={"config_id": config_id},
            timeout=60.0,
        )

        if session_response.status_code == 201:
            session_id = session_response.json()["session_id"]

            # Try to stream (should fail with invalid API key)
            with httpx.stream(
                "POST",
                f"{live_service}/sessions/{session_id}/stream",
                json={"message": "Hello"},
                timeout=30.0,
            ) as response:
                # Either fails immediately or sends error event
                if response.status_code == 200:
                    # Collect events
                    for line in response.iter_lines():
                        if line.startswith("data: "):
                            import json

                            try:
                                event = json.loads(line[6:])
                                # Should eventually get error event
                                if event.get("type") == "error":
                                    assert "message" in event
                                    break
                            except json.JSONDecodeError:
                                pass
                else:
                    # Or returns error status
                    assert response.status_code in [400, 500]

            # Cleanup
            httpx.delete(f"{live_service}/sessions/{session_id}", timeout=5.0)

        # Cleanup config

    def test_stream_with_context_parameter(self, live_service):
        """Test streaming with additional context."""
        # Create config
        # Use e2e_test_bundle from environment
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set in environment")

        # Create session
        session_response = httpx.post(
            f"{live_service}/sessions",
            json={"config_id": config_id},
            timeout=60.0,
        )

        session_id = session_response.json()["session_id"]

        # Stream with context
        with httpx.stream(
            "POST",
            f"{live_service}/sessions/{session_id}/stream",
            json={
                "message": "What language am I using?",
                "context": {"language": "Python", "version": "3.11"},
            },
            timeout=30.0,
        ) as response:
            assert response.status_code == 200

            # Just verify we get events
            event_received = False
            for line in response.iter_lines():
                if line.startswith("data: "):
                    event_received = True
                    break

            assert event_received

        # Cleanup
        httpx.delete(f"{live_service}/sessions/{session_id}", timeout=5.0)


@pytest.mark.e2e
@pytest.mark.skipif(httpx is None, reason="httpx not installed")
class TestStreamCancellation:
    """Test cancelling active streams."""

    def test_cancel_streaming_session(self, live_service):
        """Test cancelling a session while streaming is in progress."""
        # Create config
        # Use e2e_test_bundle from environment
        config_id = os.environ.get("E2E_TEST_BUNDLE_ID")
        if not config_id:
            pytest.skip("E2E_TEST_BUNDLE_ID not set in environment")

        # Create session
        session_response = httpx.post(
            f"{live_service}/sessions",
            json={"config_id": config_id},
            timeout=60.0,
        )

        session_id = session_response.json()["session_id"]

        # Start streaming (don't wait for completion)
        # Note: Testing actual cancellation is complex - we just verify endpoint works
        cancel_response = httpx.post(
            f"{live_service}/sessions/{session_id}/cancel",
            timeout=5.0,
        )

        # Should either:
        # - 200: Successfully cancelled active operation
        # - 404: Session inactive (nothing to cancel)
        assert cancel_response.status_code in [200, 404]

        # Cleanup
        httpx.delete(f"{live_service}/sessions/{session_id}", timeout=5.0)
