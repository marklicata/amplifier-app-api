"""Tests for session spawner module."""

import pytest
from amplifier_app_utils.session_spawner import (
    _generate_sub_session_id,
    merge_agent_configs,
)


class TestGenerateSubSessionId:
    """Tests for sub-session ID generation."""

    def test_basic_generation(self):
        """Test basic sub-session ID generation."""
        session_id = _generate_sub_session_id("test-agent", None, None)
        assert session_id.endswith("_test-agent")
        # Format: {16 hex}-{16 hex}_{name}
        parts = session_id.split("_")
        assert len(parts) == 2
        assert parts[1] == "test-agent"
        span_parts = parts[0].split("-")
        assert len(span_parts) == 2
        assert len(span_parts[0]) == 16
        assert len(span_parts[1]) == 16

    def test_sanitization(self):
        """Test agent name sanitization."""
        session_id = _generate_sub_session_id("Test Agent!", None, None)
        assert session_id.endswith("_test-agent")

    def test_parent_span_extraction(self):
        """Test parent span extraction from parent session ID."""
        parent_id = "1234567890abcdef-fedcba0987654321_parent"
        session_id = _generate_sub_session_id("child", parent_id, None)
        assert session_id.startswith("fedcba0987654321-")

    def test_trace_id_fallback(self):
        """Test trace ID fallback when no parent session."""
        trace_id = "0123456789abcdef0123456789abcdef"
        session_id = _generate_sub_session_id("agent", None, trace_id)
        # Should extract middle 16 chars (positions 8-24)
        assert session_id.startswith("89abcdef01234567-")

    def test_default_parent_span(self):
        """Test default parent span when no parent or trace."""
        session_id = _generate_sub_session_id("agent", None, None)
        assert session_id.startswith("0000000000000000-")


class TestMergeAgentConfigs:
    """Tests for agent config merging."""

    def test_basic_merge(self):
        """Test basic config merging."""
        parent = {
            "session": {"orchestrator": "loop-basic"},
            "providers": [{"module": "provider-anthropic"}],
        }
        overlay = {
            "providers": [{"module": "provider-openai"}],
        }
        result = merge_agent_configs(parent, overlay)
        assert len(result["providers"]) == 2

    def test_agent_filter_none(self):
        """Test agent filter with 'none'."""
        parent = {
            "agents": {"agent1": {}, "agent2": {}},
        }
        overlay = {"agents": "none"}
        result = merge_agent_configs(parent, overlay)
        assert result["agents"] == {}

    def test_agent_filter_list(self):
        """Test agent filter with list."""
        parent = {
            "agents": {"agent1": {}, "agent2": {}, "agent3": {}},
        }
        overlay = {"agents": ["agent1", "agent3"]}
        result = merge_agent_configs(parent, overlay)
        assert set(result["agents"].keys()) == {"agent1", "agent3"}

    def test_agent_filter_all(self):
        """Test agent filter with 'all' (default)."""
        parent = {
            "agents": {"agent1": {}, "agent2": {}},
        }
        overlay = {}  # No agents key = inherit all
        result = merge_agent_configs(parent, overlay)
        assert set(result["agents"].keys()) == {"agent1", "agent2"}
