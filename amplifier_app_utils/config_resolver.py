"""Configuration assembly utilities for Amplifier applications.

Provides high-level config resolution with profile, settings, and CLI override precedence.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from amplifier_profiles import compile_profile_to_mount_plan
from amplifier_profiles.merger import merge_module_items

logger = logging.getLogger(__name__)


def resolve_app_config(
    *,
    config_manager,
    profile_loader,
    agent_loader,
    provider_overrides: dict[str, Any] | None = None,
    cli_config: dict[str, Any] | None = None,
    profile_override: str | None = None,
    console=None,
) -> dict[str, Any]:
    """Resolve configuration with precedence, returning a mount plan dictionary.

    Precedence order (lowest to highest):
    1. Base defaults (basic orchestrator + context)
    2. Active profile (if any)
    3. Merged settings (user → project → local)
    4. CLI overrides
    5. Environment variable expansion

    Args:
        config_manager: ConfigManager instance
        profile_loader: ProfileLoader instance
        agent_loader: AgentLoader instance
        provider_overrides: Optional provider overrides dict
        cli_config: Optional CLI configuration overrides
        profile_override: Optional profile name to use instead of active
        console: Optional Rich console for warnings

    Returns:
        Complete mount plan dictionary ready for AmplifierSession
    """
    # 1. Base mount plan defaults
    config: dict[str, Any] = {
        "session": {
            "orchestrator": "loop-basic",
            "context": "context-simple",
        },
        "providers": [],
        "tools": [],
        "agents": [],
        "hooks": [],
    }

    provider_overrides = provider_overrides or {}

    # 2. Apply active profile (if any)
    active_profile_name = profile_override or config_manager.get_active_profile()
    provider_applied_via_profile = False

    if active_profile_name:
        try:
            profile = profile_loader.load_profile(active_profile_name)
            
            # Apply provider overrides to profile if provided
            if provider_overrides:
                profile = _apply_provider_overrides_to_profile(profile, provider_overrides)

            profile_config = compile_profile_to_mount_plan(profile, agent_loader=agent_loader)  # type: ignore[call-arg]
            config = deep_merge(config, profile_config)
            provider_applied_via_profile = bool(provider_overrides)
        except Exception as exc:  # noqa: BLE001
            message = f"Warning: Could not load profile '{active_profile_name}': {exc}"
            if console:
                console.print(f"[yellow]{message}[/yellow]")
            else:
                logger.warning(message)

    # If we have overrides but no profile applied them (no profile or failure), apply directly
    if provider_overrides and not provider_applied_via_profile:
        config["providers"] = list(provider_overrides.values())

    # 3. Apply merged settings (user → project → local)
    merged_settings = config_manager.get_merged_settings()

    modules_config = merged_settings.get("modules", {})
    settings_overlay: dict[str, Any] = {}

    for key in ("tools", "hooks", "agents"):
        if key in modules_config:
            settings_overlay[key] = modules_config[key]

    if settings_overlay:
        config = deep_merge(config, settings_overlay)

    # 4. Apply CLI overrides
    if cli_config:
        config = deep_merge(config, cli_config)

    # 5. Expand environment variables
    return expand_env_vars(config)


def _apply_provider_overrides_to_profile(profile: dict, provider_overrides: dict[str, Any]) -> dict:
    """Apply provider overrides to a profile's providers list."""
    if not provider_overrides:
        return profile

    # Get existing providers from profile
    existing_providers = profile.get("providers", [])
    
    # Create a new list with overrides applied
    overridden_providers = []
    override_keys = set(provider_overrides.keys())
    
    # Update existing providers
    for provider in existing_providers:
        if isinstance(provider, dict) and "module" in provider:
            module_id = provider["module"]
            if module_id in provider_overrides:
                # Merge override
                overridden_providers.append({**provider, **provider_overrides[module_id]})
                override_keys.discard(module_id)
            else:
                overridden_providers.append(provider)
        else:
            overridden_providers.append(provider)
    
    # Add new providers from overrides
    for key in override_keys:
        overridden_providers.append(provider_overrides[key])
    
    # Update profile
    profile["providers"] = overridden_providers
    return profile


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Deep merge dictionaries with special handling for module lists.

    Module lists (providers, tools, hooks, agents) are merged by module ID,
    with overlays taking precedence for matching modules.

    Args:
        base: Base configuration dictionary
        overlay: Overlay configuration to merge in

    Returns:
        Merged configuration dictionary
    """
    result = base.copy()

    module_list_keys = {"providers", "tools", "hooks", "agents"}

    for key, value in overlay.items():
        if key in module_list_keys and key in result:
            if isinstance(result[key], list) and isinstance(value, list):
                result[key] = _merge_module_lists(result[key], value)
            else:
                result[key] = value
        elif key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def _merge_module_lists(
    base_modules: list[dict[str, Any]], overlay_modules: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Merge module lists on module ID, with deep merging.

    Delegates to canonical merger.merge_module_items for DRY compliance.
    See amplifier_profiles.merger for complete merge strategy documentation.

    Args:
        base_modules: Base list of module configs
        overlay_modules: Overlay list of module configs

    Returns:
        Merged list of module configs
    """
    # Build dict by ID for efficient lookup
    result_dict: dict[str, dict[str, Any]] = {}

    # Add all base modules
    for module in base_modules:
        if isinstance(module, dict) and "module" in module:
            result_dict[module["module"]] = module

    # Merge or add overlay modules
    for module in overlay_modules:
        if isinstance(module, dict) and "module" in module:
            module_id = module["module"]
            if module_id in result_dict:
                # Module exists in base - deep merge using canonical function
                result_dict[module_id] = merge_module_items(result_dict[module_id], module)
            else:
                # New module in overlay - add it
                result_dict[module_id] = module

    # Return as list, preserving base order + new overlays
    result = []
    seen_ids: set[str] = set()

    for module in base_modules:
        if isinstance(module, dict) and "module" in module:
            module_id = module["module"]
            if module_id not in seen_ids:
                result.append(result_dict[module_id])
                seen_ids.add(module_id)

    for module in overlay_modules:
        if isinstance(module, dict) and "module" in module:
            module_id = module["module"]
            if module_id not in seen_ids:
                result.append(module)
                seen_ids.add(module_id)

    return result


ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::([^}]*))?}")


def expand_env_vars(config: dict[str, Any]) -> dict[str, Any]:
    """Expand ${VAR} and ${VAR:default} references within configuration values.

    Recursively processes dictionaries, lists, and strings.

    Args:
        config: Configuration dictionary to process

    Returns:
        Configuration with environment variables expanded
    """

    def replace_value(value: Any) -> Any:
        if isinstance(value, str):
            return ENV_PATTERN.sub(_replace_match, value)
        if isinstance(value, dict):
            return {k: replace_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [replace_value(item) for item in value]
        return value

    def _replace_match(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default = match.group(2)
        return os.environ.get(var_name, default if default is not None else "")

    return replace_value(config)


__all__ = ["resolve_app_config", "deep_merge", "expand_env_vars"]
