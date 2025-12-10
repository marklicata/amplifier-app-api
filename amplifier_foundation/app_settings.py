"""High-level application settings helpers for Amplifier applications.

These helpers provide a clean interface for reading and writing application settings
across different scopes (local/project/global) without directly manipulating YAML files.

This is a key foundation component that provides:
- Scope-aware provider override management
- Profile merging with overrides
- Settings file path resolution
- Type-safe scope operations
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from amplifier_config import ConfigManager, Scope
from amplifier_profiles.schema import ModuleConfig, Profile

from .provider_sources import DEFAULT_PROVIDER_SOURCES

ScopeType = Literal["local", "project", "global"]

_SCOPE_MAP: dict[ScopeType, Scope] = {
    "local": Scope.LOCAL,
    "project": Scope.PROJECT,
    "global": Scope.USER,
}


class AppSettings:
    """High-level helpers for reading and writing Amplifier application settings.
    
    This class provides a simplified interface for managing application configuration
    across different scopes. It handles the complexity of YAML file manipulation and
    scope resolution, presenting a clean API for application developers.
    
    Example:
        ```python
        from amplifier_foundation import PathManager, AppSettings
        
        pm = PathManager(app_name="my-app")
        config = pm.create_config_manager()
        settings = AppSettings(config)
        
        # Set provider at global scope
        settings.set_provider_override(
            {"module": "provider-anthropic", "config": {"model": "claude-3-5-sonnet-20241022"}},
            "global"
        )
        
        # Get merged provider overrides
        providers = settings.get_provider_overrides()
        print(f"Active provider: {providers[0]['module']}")
        
        # Clear local override
        settings.clear_provider_override("local")
        ```
    """

    def __init__(self, config_manager: ConfigManager):
        """Initialize app settings.
        
        Args:
            config_manager: ConfigManager instance from PathManager
        """
        self._config = config_manager

    # ----- Scope helpers -----

    def _scope_enum(self, scope: ScopeType) -> Scope:
        """Convert ScopeType string to Scope enum."""
        return _SCOPE_MAP[scope]

    def scope_path(self, scope: ScopeType) -> Path | None:
        """Return the filesystem path for a scope, or None if scope is disabled.
        
        Args:
            scope: Scope to resolve (local/project/global)
            
        Returns:
            Path to settings file, or None if scope doesn't exist
        """
        return self._config.scope_to_path(self._scope_enum(scope))

    # ----- Provider overrides -----

    def set_provider_override(self, provider_entry: dict[str, Any], scope: ScopeType) -> None:
        """Persist provider override at a specific scope.
        
        Args:
            provider_entry: Provider config dict with 'module', 'config', and optional 'source'
            scope: Where to save (local/project/global)
        """
        self._config.update_settings({"config": {"providers": [provider_entry]}}, scope=self._scope_enum(scope))

    def clear_provider_override(self, scope: ScopeType) -> bool:
        """Clear provider override from a scope.
        
        Args:
            scope: Which scope to clear (local/project/global)
            
        Returns:
            True if override was found and cleared, False if nothing to clear
        """
        scope_path = self.scope_path(scope)
        scope_settings = self._config._read_yaml(scope_path) or {}  # type: ignore[attr-defined]
        config_section = scope_settings.get("config") or {}
        providers = config_section.get("providers")

        if isinstance(providers, list) and providers:
            config_section.pop("providers", None)

            if config_section:
                scope_settings["config"] = config_section
            elif "config" in scope_settings:
                scope_settings.pop("config", None)

            self._config._write_yaml(scope_path, scope_settings)  # type: ignore[attr-defined]
            return True

        return False

    def get_provider_overrides(self) -> list[dict[str, Any]]:
        """Return merged provider overrides (local > project > global).
        
        Returns:
            List of provider config dicts in priority order
        """
        merged = self._config.get_merged_settings()
        providers = merged.get("config", {}).get("providers", [])
        return providers if isinstance(providers, list) else []

    def get_scope_provider_overrides(self, scope: ScopeType) -> list[dict[str, Any]]:
        """Return provider overrides defined at a specific scope.
        
        Args:
            scope: Which scope to read from (local/project/global)
            
        Returns:
            List of provider config dicts from that scope only
        """
        scope_path = self.scope_path(scope)
        scope_settings = self._config._read_yaml(scope_path) or {}  # type: ignore[attr-defined]
        config_section = scope_settings.get("config") or {}
        providers = config_section.get("providers", [])
        return providers if isinstance(providers, list) else []

    def apply_provider_overrides_to_profile(
        self, profile: Profile, overrides: list[dict[str, Any]] | None = None
    ) -> Profile:
        """Return a copy of `profile` with provider overrides applied.
        
        This merges provider configuration from settings into profile providers,
        giving precedence to overrides. Useful for preparing profiles for runtime.
        
        Args:
            profile: Base profile to merge overrides into
            overrides: Optional explicit overrides (uses get_provider_overrides() if None)
            
        Returns:
            New Profile instance with overrides applied
        """
        provider_overrides = overrides if overrides is not None else self.get_provider_overrides()
        if not provider_overrides:
            return profile

        normalized_overrides: dict[str, dict[str, Any]] = {}
        for entry in provider_overrides:
            module_id = entry.get("module")
            if module_id and "source" not in entry:
                canonical = DEFAULT_PROVIDER_SOURCES.get(module_id)
                if canonical:
                    entry = {**entry, "source": canonical}
            if module_id:
                normalized_overrides[module_id] = entry

        providers: list[ModuleConfig] = []

        for provider in profile.providers or []:
            override_entry = normalized_overrides.pop(provider.module, None)
            if override_entry:
                merged_config = {**(provider.config or {}), **(override_entry.get("config") or {})}
                provider = ModuleConfig(
                    module=provider.module,
                    source=override_entry.get("source", provider.source),
                    config=merged_config or None,
                )
            providers.append(provider)

        # Append any additional providers specified only in overrides
        for _module_id, entry in normalized_overrides.items():
            providers.append(ModuleConfig.model_validate(entry))

        return profile.model_copy(update={"providers": providers})


__all__ = ["AppSettings", "ScopeType"]
