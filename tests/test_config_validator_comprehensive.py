"""Comprehensive tests for ConfigValidator.

Tests all validation rules for Amplifier config YAML structure.
"""

import pytest

from amplifier_app_api.core.config_validator import ConfigValidationError, ConfigValidator


class TestBundleSection:
    """Test bundle section validation."""

    def test_missing_bundle_section(self):
        """Test that missing bundle section raises error."""
        config = {
            "providers": [{"module": "provider-anthropic"}],
        }
        with pytest.raises(ConfigValidationError, match="Missing required section: 'bundle'"):
            ConfigValidator.validate(config)

    def test_bundle_not_a_dict(self):
        """Test that bundle must be a dict."""
        config = {"bundle": "not a dict"}
        with pytest.raises(ConfigValidationError, match="must be a dict"):
            ConfigValidator.validate(config)

    def test_missing_bundle_name(self):
        """Test that bundle.name is required."""
        config = {"bundle": {"version": "1.0.0"}}
        with pytest.raises(ConfigValidationError, match="Missing required field: 'bundle.name'"):
            ConfigValidator.validate(config)

    def test_bundle_name_empty_string(self):
        """Test that bundle.name cannot be empty."""
        config = {"bundle": {"name": ""}}
        with pytest.raises(ConfigValidationError, match="bundle.name must be a non-empty string"):
            ConfigValidator.validate(config)

    def test_bundle_name_not_string(self):
        """Test that bundle.name must be a string."""
        config = {"bundle": {"name": 12345}}
        with pytest.raises(ConfigValidationError, match="bundle.name must be a non-empty string"):
            ConfigValidator.validate(config)

    def test_valid_minimal_bundle(self):
        """Test minimal valid bundle section."""
        config = {"bundle": {"name": "test-bundle"}}
        ConfigValidator.validate(config)  # Should not raise

    def test_valid_bundle_with_optional_fields(self):
        """Test bundle with version and description."""
        config = {
            "bundle": {
                "name": "test-bundle",
                "version": "1.0.0",
                "description": "Test bundle",
            }
        }
        ConfigValidator.validate(config)  # Should not raise


class TestIncludesSection:
    """Test includes section validation."""

    def test_includes_must_be_list(self):
        """Test that includes must be a list."""
        config = {
            "bundle": {"name": "test"},
            "includes": "not a list",
        }
        with pytest.raises(ConfigValidationError, match="includes must be a list"):
            ConfigValidator.validate(config)

    def test_includes_item_must_be_dict(self):
        """Test that each include must be a dict."""
        config = {
            "bundle": {"name": "test"},
            "includes": ["not a dict"],
        }
        with pytest.raises(ConfigValidationError, match="includes\\[0\\] must be a dict"):
            ConfigValidator.validate(config)

    def test_includes_item_missing_bundle_field(self):
        """Test that include items must have bundle field."""
        config = {
            "bundle": {"name": "test"},
            "includes": [{"source": "git+https://example.com"}],
        }
        with pytest.raises(ConfigValidationError, match="includes\\[0\\] missing 'bundle' field"):
            ConfigValidator.validate(config)

    def test_valid_includes(self):
        """Test valid includes section."""
        config = {
            "bundle": {"name": "test"},
            "includes": [
                {"bundle": "foundation"},
                {"bundle": "git+https://github.com/example/bundle@main"},
            ],
        }
        ConfigValidator.validate(config)  # Should not raise

    def test_includes_section_optional(self):
        """Test that includes section is optional."""
        config = {"bundle": {"name": "test"}}
        ConfigValidator.validate(config)  # Should not raise


class TestProvidersSection:
    """Test providers section validation."""

    def test_providers_must_be_list(self):
        """Test that providers must be a list."""
        config = {
            "bundle": {"name": "test"},
            "providers": "not a list",
        }
        with pytest.raises(ConfigValidationError, match="providers must be a list"):
            ConfigValidator.validate(config)

    def test_provider_item_must_be_dict(self):
        """Test that each provider must be a dict."""
        config = {
            "bundle": {"name": "test"},
            "providers": ["not a dict"],
        }
        with pytest.raises(ConfigValidationError, match="providers\\[0\\] must be a dict"):
            ConfigValidator.validate(config)

    def test_provider_missing_module_field(self):
        """Test that provider must have module field."""
        config = {
            "bundle": {"name": "test"},
            "providers": [{"config": {"api_key": "test"}}],
        }
        with pytest.raises(ConfigValidationError, match="providers\\[0\\] missing 'module' field"):
            ConfigValidator.validate(config)

    def test_valid_providers(self):
        """Test valid providers section."""
        config = {
            "bundle": {"name": "test"},
            "providers": [
                {
                    "module": "provider-anthropic",
                    "config": {"api_key": "test", "model": "claude-sonnet-4-5"},
                },
                {
                    "module": "provider-openai",
                    "source": "git+https://example.com/provider",
                },
            ],
        }
        ConfigValidator.validate(config)  # Should not raise

    def test_providers_section_optional(self):
        """Test that providers section is optional."""
        config = {"bundle": {"name": "test"}}
        ConfigValidator.validate(config)  # Should not raise


class TestToolsSection:
    """Test tools section validation."""

    def test_tools_must_be_list(self):
        """Test that tools must be a list."""
        config = {
            "bundle": {"name": "test"},
            "tools": "not a list",
        }
        with pytest.raises(ConfigValidationError, match="tools must be a list"):
            ConfigValidator.validate(config)

    def test_tool_item_must_be_dict(self):
        """Test that each tool must be a dict."""
        config = {
            "bundle": {"name": "test"},
            "tools": ["not a dict"],
        }
        with pytest.raises(ConfigValidationError, match="tools\\[0\\] must be a dict"):
            ConfigValidator.validate(config)

    def test_tool_missing_module_field(self):
        """Test that tool must have module field."""
        config = {
            "bundle": {"name": "test"},
            "tools": [{"source": "git+https://example.com"}],
        }
        with pytest.raises(ConfigValidationError, match="tools\\[0\\] missing 'module' field"):
            ConfigValidator.validate(config)

    def test_valid_tools(self):
        """Test valid tools section."""
        config = {
            "bundle": {"name": "test"},
            "tools": [
                {"module": "tool-filesystem"},
                {"module": "tool-bash", "source": "git+https://example.com/tool"},
                {"module": "tool-web", "config": {"timeout": 30}},
            ],
        }
        ConfigValidator.validate(config)  # Should not raise

    def test_tools_section_optional(self):
        """Test that tools section is optional."""
        config = {"bundle": {"name": "test"}}
        ConfigValidator.validate(config)  # Should not raise


class TestHooksSection:
    """Test hooks section validation."""

    def test_hooks_must_be_list(self):
        """Test that hooks must be a list."""
        config = {
            "bundle": {"name": "test"},
            "hooks": "not a list",
        }
        with pytest.raises(ConfigValidationError, match="hooks must be a list"):
            ConfigValidator.validate(config)

    def test_hook_item_must_be_dict(self):
        """Test that each hook must be a dict."""
        config = {
            "bundle": {"name": "test"},
            "hooks": ["not a dict"],
        }
        with pytest.raises(ConfigValidationError, match="hooks\\[0\\] must be a dict"):
            ConfigValidator.validate(config)

    def test_hook_missing_module_field(self):
        """Test that hook must have module field."""
        config = {
            "bundle": {"name": "test"},
            "hooks": [{"config": {}}],
        }
        with pytest.raises(ConfigValidationError, match="hooks\\[0\\] missing 'module' field"):
            ConfigValidator.validate(config)

    def test_valid_hooks(self):
        """Test valid hooks section."""
        config = {
            "bundle": {"name": "test"},
            "hooks": [
                {"module": "hooks-logging"},
                {"module": "hooks-approval", "config": {"auto_approve": False}},
            ],
        }
        ConfigValidator.validate(config)  # Should not raise

    def test_hooks_section_optional(self):
        """Test that hooks section is optional."""
        config = {"bundle": {"name": "test"}}
        ConfigValidator.validate(config)  # Should not raise


class TestSpawnSection:
    """Test spawn section validation."""

    def test_spawn_must_be_dict(self):
        """Test that spawn must be a dict."""
        config = {
            "bundle": {"name": "test"},
            "spawn": "not a dict",
        }
        with pytest.raises(ConfigValidationError, match="spawn must be a dict"):
            ConfigValidator.validate(config)

    def test_spawn_exclude_tools_must_be_list(self):
        """Test that spawn.exclude_tools must be a list."""
        config = {
            "bundle": {"name": "test"},
            "spawn": {"exclude_tools": "not a list"},
        }
        with pytest.raises(ConfigValidationError, match="spawn.exclude_tools must be a list"):
            ConfigValidator.validate(config)

    def test_spawn_tools_must_be_list(self):
        """Test that spawn.tools must be a list."""
        config = {
            "bundle": {"name": "test"},
            "spawn": {"tools": "not a list"},
        }
        with pytest.raises(ConfigValidationError, match="spawn.tools must be a list"):
            ConfigValidator.validate(config)

    def test_spawn_cannot_have_both_tools_and_exclude_tools(self):
        """Test that spawn cannot have both tools and exclude_tools."""
        config = {
            "bundle": {"name": "test"},
            "spawn": {
                "tools": ["tool-bash"],
                "exclude_tools": ["tool-task"],
            },
        }
        with pytest.raises(
            ConfigValidationError,
            match="spawn cannot have both 'exclude_tools' and 'tools'",
        ):
            ConfigValidator.validate(config)

    def test_valid_spawn_with_exclude_tools(self):
        """Test valid spawn with exclude_tools."""
        config = {
            "bundle": {"name": "test"},
            "spawn": {
                "exclude_tools": ["tool-task", "tool-bash"],
            },
        }
        ConfigValidator.validate(config)  # Should not raise

    def test_valid_spawn_with_tools(self):
        """Test valid spawn with tools list."""
        config = {
            "bundle": {"name": "test"},
            "spawn": {
                "tools": ["tool-filesystem", "tool-web"],
            },
        }
        ConfigValidator.validate(config)  # Should not raise

    def test_spawn_section_optional(self):
        """Test that spawn section is optional."""
        config = {"bundle": {"name": "test"}}
        ConfigValidator.validate(config)  # Should not raise


class TestCompleteConfigs:
    """Test validation of complete config examples."""

    def test_minimal_valid_config(self):
        """Test minimal valid configuration."""
        config = {
            "bundle": {"name": "minimal"},
        }
        ConfigValidator.validate(config)  # Should not raise

    def test_complete_valid_config(self):
        """Test complete configuration with all sections."""
        config = {
            "bundle": {
                "name": "complete-config",
                "version": "1.0.0",
                "description": "Complete test config",
            },
            "includes": [
                {"bundle": "foundation"},
            ],
            "providers": [
                {
                    "module": "provider-anthropic",
                    "config": {
                        "api_key": "${ANTHROPIC_API_KEY}",
                        "model": "claude-sonnet-4-5",
                    },
                },
            ],
            "tools": [
                {"module": "tool-filesystem"},
                {"module": "tool-bash"},
            ],
            "hooks": [
                {"module": "hooks-logging"},
            ],
            "spawn": {
                "exclude_tools": ["tool-task"],
            },
        }
        ConfigValidator.validate(config)  # Should not raise

    def test_config_with_unknown_sections_accepted(self):
        """Test that unknown sections don't cause validation errors."""
        config = {
            "bundle": {"name": "test"},
            "custom_section": {
                "some_field": "some_value",
            },
            "session": {
                "orchestrator": "loop-basic",
                "context": "context-simple",
            },
        }
        # Should not raise - validator only checks required sections
        ConfigValidator.validate(config)


class TestEdgeCases:
    """Test edge cases and error messages."""

    def test_empty_config(self):
        """Test empty config dict."""
        config = {}
        with pytest.raises(ConfigValidationError):
            ConfigValidator.validate(config)

    def test_multiple_validation_errors_shows_first(self):
        """Test that validation shows first error when multiple exist."""
        config = {
            # Missing bundle section entirely
            "providers": "not even a list",
        }
        with pytest.raises(ConfigValidationError, match="Missing required section"):
            ConfigValidator.validate(config)

    def test_null_bundle_section(self):
        """Test that None bundle section fails."""
        config = {"bundle": None}
        with pytest.raises(ConfigValidationError, match="must be a dict"):
            ConfigValidator.validate(config)

    def test_array_at_top_level_fails(self):
        """Test that top-level config cannot be an array."""
        # This would be caught by YAML parsing before validation
        # The validator expects a dict, not a list
        # This is a documentation test showing the expectation
        pass

    def test_complex_nested_structure_validates(self):
        """Test that complex nested structures pass validation."""
        config = {
            "bundle": {"name": "complex"},
            "providers": [
                {
                    "module": "provider-anthropic",
                    "config": {
                        "api_key": "${ANTHROPIC_API_KEY}",
                        "model": "claude-sonnet-4-5",
                        "options": {
                            "enable_1m_context": False,
                            "priority": 1,
                            "fallback": {
                                "model": "claude-haiku",
                                "max_retries": 3,
                            },
                        },
                    },
                },
            ],
        }
        ConfigValidator.validate(config)  # Should not raise
