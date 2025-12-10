"""Module configuration management for Amplifier applications.

Provides high-level interface for adding, removing, and listing modules
(tools, hooks, agents, providers, orchestrators, contexts) across different
configuration scopes.
"""

import logging
from dataclasses import dataclass
from typing import Any, Literal

from amplifier_config import ConfigManager

logger = logging.getLogger(__name__)

ScopeType = Literal["local", "project", "global"]
ModuleType = Literal["tool", "hook", "agent", "provider", "orchestrator", "context"]


@dataclass
class ModuleInfo:
    """Information about a loaded module."""

    module_id: str
    module_type: str
    source: str


@dataclass
class AddModuleResult:
    """Result of adding a module."""

    module_id: str
    module_type: str
    scope: str
    file: str


@dataclass
class RemoveModuleResult:
    """Result of removing a module."""

    module_id: str
    scope: str


class ModuleManager:
    """Manage module configuration.
    
    This class provides a high-level interface for managing Amplifier modules
    across different scopes. It handles YAML manipulation and provides clean
    results for UI display.
    
    Example:
        ```python
        from amplifier_foundation import PathManager, ModuleManager
        
        pm = PathManager(app_name="my-app")
        config = pm.create_config_manager()
        mgr = ModuleManager(config)
        
        # Add a tool at project scope
        result = mgr.add_module(
            module_id="tool-shell",
            module_type="tool",
            scope="project",
            source="git+https://github.com/example/tool-shell"
        )
        print(f"Added {result.module_id} to {result.file}")
        
        # List current modules
        modules = mgr.get_current_modules()
        for mod in modules:
            print(f"{mod.module_type}: {mod.module_id}")
        
        # Remove a module
        mgr.remove_module("tool-shell", "project")
        ```
    """

    def __init__(self, config_manager: ConfigManager):
        """Initialize module manager.

        Args:
            config_manager: Config manager instance
        """
        self.settings = config_manager

    def add_module(
        self,
        module_id: str,
        module_type: ModuleType,
        scope: ScopeType,
        config: dict | None = None,
        source: str | None = None,
    ) -> AddModuleResult:
        """Add module to configuration at scope.

        Args:
            module_id: Module identifier
            module_type: Type of module (tool/hook/agent/provider/orchestrator/context)
            scope: Where to save (local/project/global)
            config: Optional module configuration
            source: Optional source URI (git+https://... or file path)

        Returns:
            AddModuleResult with details
        """
        module_entry: dict[str, Any] = {"module": module_id}
        if source:
            module_entry["source"] = source
        if config:
            module_entry["config"] = config

        # Map module type to settings key (tools/hooks/agents/providers/orchestrators/contexts)
        type_to_key = {
            "tool": "tools",
            "hook": "hooks",
            "agent": "agents",
            "provider": "providers",
            "orchestrator": "orchestrators",
            "context": "contexts",
        }
        module_list_key = type_to_key[module_type]

        # Get current modules list
        scope_map = {"local": "local", "project": "project", "global": "user"}
        settings_scope = scope_map[scope]
        target_file = self._get_file_for_scope(settings_scope)

        settings = self.settings._read_yaml(target_file) or {}  # type: ignore[attr-defined]
        if "modules" not in settings:
            settings["modules"] = {}
        if module_list_key not in settings["modules"]:
            settings["modules"][module_list_key] = []

        # Add module (avoid duplicates)
        existing_ids = {m.get("module") for m in settings["modules"][module_list_key] if isinstance(m, dict)}
        if module_id not in existing_ids:
            settings["modules"][module_list_key].append(module_entry)
            self.settings._write_yaml(target_file, settings)  # type: ignore[attr-defined]
            logger.info(f"Added {module_type} '{module_id}' at {scope} scope")
        else:
            logger.warning(f"Module '{module_id}' already exists at {scope} scope")

        return AddModuleResult(module_id=module_id, module_type=module_type, scope=scope, file=str(target_file))

    def remove_module(
        self,
        module_id: str,
        scope: ScopeType,
    ) -> RemoveModuleResult:
        """Remove module from configuration at scope.

        Args:
            module_id: Module identifier
            scope: Which scope to remove from

        Returns:
            RemoveModuleResult with details
        """
        scope_map = {"local": "local", "project": "project", "global": "user"}
        settings_scope = scope_map[scope]
        target_file = self._get_file_for_scope(settings_scope)

        settings = self.settings._read_yaml(target_file)  # type: ignore[attr-defined]
        if not settings or "modules" not in settings:
            logger.warning(f"No modules configured at {scope} scope")
            return RemoveModuleResult(module_id=module_id, scope=scope)

        # Remove from all module types
        removed = False
        for module_type in ["tools", "hooks", "agents", "providers", "orchestrators", "contexts"]:
            if module_type in settings["modules"]:
                original_len = len(settings["modules"][module_type])
                settings["modules"][module_type] = [
                    m for m in settings["modules"][module_type] if m.get("module") != module_id
                ]
                if len(settings["modules"][module_type]) < original_len:
                    removed = True

                # Clean up empty list
                if not settings["modules"][module_type]:
                    del settings["modules"][module_type]

        # Clean up empty modules section
        if not settings["modules"]:
            del settings["modules"]

        if removed:
            self.settings._write_yaml(target_file, settings)  # type: ignore[attr-defined]
            logger.info(f"Removed module '{module_id}' from {scope} scope")
        else:
            logger.warning(f"Module '{module_id}' not found at {scope} scope")

        return RemoveModuleResult(module_id=module_id, scope=scope)

    def get_current_modules(self) -> list[ModuleInfo]:
        """Get currently configured modules from merged settings.

        Returns:
            List of ModuleInfo objects
        """
        merged = self.settings.get_merged_settings()
        modules = []

        if "modules" in merged:
            module_config = merged["modules"]

            # Map settings keys to module types
            key_to_type = {
                "tools": "tool",
                "hooks": "hook",
                "agents": "agent",
                "providers": "provider",
                "orchestrators": "orchestrator",
                "contexts": "context",
            }

            # Collect all module types
            for settings_key, module_type in key_to_type.items():
                if settings_key in module_config:
                    for item in module_config[settings_key]:
                        if isinstance(item, dict) and "module" in item:
                            modules.append(
                                ModuleInfo(module_id=item["module"], module_type=module_type, source="settings")
                            )

        return modules

    def _get_file_for_scope(self, scope: str):
        """Get settings file path for scope."""
        if scope == "user":
            return self.settings.paths.user
        if scope == "project":
            return self.settings.paths.project
        # local
        return self.settings.paths.local


__all__ = [
    "ModuleManager",
    "ModuleInfo",
    "AddModuleResult",
    "RemoveModuleResult",
    "ModuleType",
    "ScopeType",
]
