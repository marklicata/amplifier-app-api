"""Tests for config resolver module."""

import os

import pytest
from amplifier_app_utils.config_resolver import (
    deep_merge,
    expand_env_vars,
)


class TestDeepMerge:
    """Tests for deep merge functionality."""

    def test_simple_merge(self):
        """Test simple dictionary merge."""
        base = {"a": 1, "b": 2}
        overlay = {"b": 3, "c": 4}
        result = deep_merge(base, overlay)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        """Test nested dictionary merge."""
        base = {"outer": {"inner": {"a": 1}}}
        overlay = {"outer": {"inner": {"b": 2}}}
        result = deep_merge(base, overlay)
        assert result == {"outer": {"inner": {"a": 1, "b": 2}}}

    def test_module_list_merge(self):
        """Test module list merging by ID."""
        base = {
            "providers": [
                {"module": "provider-anthropic", "config": {"a": 1}},
                {"module": "provider-openai"},
            ]
        }
        overlay = {
            "providers": [
                {"module": "provider-anthropic", "config": {"b": 2}},
                {"module": "provider-azure"},
            ]
        }
        result = deep_merge(base, overlay)
        # Should have 3 providers: merged anthropic, original openai, new azure
        assert len(result["providers"]) == 3
        
        # Find anthropic provider - should be merged
        anthropic = next(p for p in result["providers"] if p["module"] == "provider-anthropic")
        assert anthropic["config"]["a"] == 1
        assert anthropic["config"]["b"] == 2

    def test_list_replacement(self):
        """Test that non-module lists are replaced."""
        base = {"normal_list": [1, 2, 3]}
        overlay = {"normal_list": [4, 5]}
        result = deep_merge(base, overlay)
        assert result["normal_list"] == [4, 5]


class TestExpandEnvVars:
    """Tests for environment variable expansion."""

    def test_simple_expansion(self):
        """Test simple variable expansion."""
        os.environ["TEST_VAR"] = "test_value"
        config = {"key": "${TEST_VAR}"}
        result = expand_env_vars(config)
        assert result["key"] == "test_value"

    def test_default_value(self):
        """Test default value when variable not set."""
        config = {"key": "${NONEXISTENT_VAR:default}"}
        result = expand_env_vars(config)
        assert result["key"] == "default"

    def test_nested_expansion(self):
        """Test expansion in nested structures."""
        os.environ["TEST_VAR"] = "nested_value"
        config = {
            "outer": {
                "inner": "${TEST_VAR}",
                "list": ["${TEST_VAR}", "static"],
            }
        }
        result = expand_env_vars(config)
        assert result["outer"]["inner"] == "nested_value"
        assert result["outer"]["list"][0] == "nested_value"

    def test_no_expansion_needed(self):
        """Test that non-string values are preserved."""
        config = {
            "string": "plain",
            "number": 42,
            "bool": True,
            "none": None,
        }
        result = expand_env_vars(config)
        assert result == config

    def test_empty_default(self):
        """Test empty string default."""
        config = {"key": "${NONEXISTENT_VAR}"}
        result = expand_env_vars(config)
        assert result["key"] == ""
