"""Configuration validation for Amplifier configs."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ConfigValidationError(ValueError):
    """Raised when config validation fails."""

    pass


class ConfigValidator:
    """Validates Amplifier config YAML structure and required fields."""

    REQUIRED_FIELDS = {
        "bundle": {"name"},  # bundle.name is required
    }

    OPTIONAL_SECTIONS = {
        "includes",
        "providers",
        "tools",
        "hooks",
        "agents",
        "spawn",
        "context",
        "orchestrator",
    }

    @classmethod
    def validate(cls, config_dict: dict[str, Any]) -> None:
        """Validate config structure and required fields.

        Args:
            config_dict: Parsed YAML config as dict

        Raises:
            ConfigValidationError: If validation fails
        """
        # Check required top-level sections
        for section, required_fields in cls.REQUIRED_FIELDS.items():
            if section not in config_dict:
                raise ConfigValidationError(f"Missing required section: '{section}'")

            section_data = config_dict[section]
            if not isinstance(section_data, dict):
                raise ConfigValidationError(
                    f"Section '{section}' must be a dict, got {type(section_data).__name__}"
                )

            # Check required fields within section
            for field in required_fields:
                if field not in section_data:
                    raise ConfigValidationError(f"Missing required field: '{section}.{field}'")

        # Validate bundle.name is non-empty
        bundle_name = config_dict["bundle"].get("name")
        if not bundle_name or not isinstance(bundle_name, str):
            raise ConfigValidationError("bundle.name must be a non-empty string")

        # Validate optional sections if present
        cls._validate_includes(config_dict.get("includes"))
        cls._validate_providers(config_dict.get("providers"))
        cls._validate_tools(config_dict.get("tools"))
        cls._validate_hooks(config_dict.get("hooks"))
        cls._validate_spawn(config_dict.get("spawn"))

        logger.debug("Config validation passed")

    @classmethod
    def _validate_includes(cls, includes: Any) -> None:
        """Validate includes section."""
        if includes is None:
            return

        if not isinstance(includes, list):
            raise ConfigValidationError("includes must be a list")

        for i, include in enumerate(includes):
            if not isinstance(include, dict):
                raise ConfigValidationError(f"includes[{i}] must be a dict")
            if "bundle" not in include:
                raise ConfigValidationError(f"includes[{i}] missing 'bundle' field")

    @classmethod
    def _validate_providers(cls, providers: Any) -> None:
        """Validate providers section."""
        if providers is None:
            return

        if not isinstance(providers, list):
            raise ConfigValidationError("providers must be a list")

        for i, provider in enumerate(providers):
            if not isinstance(provider, dict):
                raise ConfigValidationError(f"providers[{i}] must be a dict")
            if "module" not in provider:
                raise ConfigValidationError(f"providers[{i}] missing 'module' field")

    @classmethod
    def _validate_tools(cls, tools: Any) -> None:
        """Validate tools section."""
        if tools is None:
            return

        if not isinstance(tools, list):
            raise ConfigValidationError("tools must be a list")

        for i, tool in enumerate(tools):
            if not isinstance(tool, dict):
                raise ConfigValidationError(f"tools[{i}] must be a dict")
            if "module" not in tool:
                raise ConfigValidationError(f"tools[{i}] missing 'module' field")
            # source is technically required but we'll be lenient for now
            # (could be installed package)

    @classmethod
    def _validate_hooks(cls, hooks: Any) -> None:
        """Validate hooks section."""
        if hooks is None:
            return

        if not isinstance(hooks, list):
            raise ConfigValidationError("hooks must be a list")

        for i, hook in enumerate(hooks):
            if not isinstance(hook, dict):
                raise ConfigValidationError(f"hooks[{i}] must be a dict")
            if "module" not in hook:
                raise ConfigValidationError(f"hooks[{i}] missing 'module' field")

    @classmethod
    def _validate_spawn(cls, spawn: Any) -> None:
        """Validate spawn section."""
        if spawn is None:
            return

        if not isinstance(spawn, dict):
            raise ConfigValidationError("spawn must be a dict")

        # Can have either exclude_tools OR tools, not both
        has_exclude = "exclude_tools" in spawn
        has_tools = "tools" in spawn

        if has_exclude and has_tools:
            raise ConfigValidationError(
                "spawn cannot have both 'exclude_tools' and 'tools' - use one or the other"
            )

        if has_exclude:
            if not isinstance(spawn["exclude_tools"], list):
                raise ConfigValidationError("spawn.exclude_tools must be a list")

        if has_tools:
            if not isinstance(spawn["tools"], list):
                raise ConfigValidationError("spawn.tools must be a list")
