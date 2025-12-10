"""Amplifier Foundation - Common library for building Amplifier applications.

This package provides a unified, high-level API for building applications on top
of the Amplifier AI development platform. It orchestrates the core amplifier
dependencies (amplifier-core, amplifier-config, amplifier-module-resolution,
amplifier-collections, amplifier-profiles) to provide a simple, cohesive interface.

Quick Start:
    ```python
    from amplifier_foundation import PathManager, ProviderManager, SessionStore
    
    # Set up paths and configuration
    pm = PathManager(app_name="my-app")
    config = pm.create_config_manager()
    
    # Manage providers
    provider_mgr = ProviderManager(config)
    provider_mgr.use_provider(
        provider_id="provider-anthropic",
        scope="global",
        config={"model": "claude-3-5-sonnet-20241022"}
    )
    
    # Store session data
    store = SessionStore()
    store.save_session("my-session", {"messages": [...]})
    ```

Components:
    - PathManager: Path and configuration management with dependency injection
    - ProviderManager: Provider configuration and discovery
    - ModuleManager: Module configuration (tools, hooks, agents, etc.)
    - SessionStore: Session persistence with atomic writes
    - SessionSpawner: Agent delegation and sub-session management
    - KeyManager: Secure API key storage
    - AppSettings: High-level settings helpers
    - ConfigResolver: Configuration assembly with precedence
    - Various utilities for mentions, projects, and provider sources
"""

from .app_settings import AppSettings, ScopeType
from .config_resolver import deep_merge, expand_env_vars, resolve_app_config
from .effective_config import EffectiveConfigSummary, get_effective_config_summary
from .key_manager import KeyManager
from .module_manager import (
    AddModuleResult,
    ModuleInfo,
    ModuleManager,
    ModuleType,
    RemoveModuleResult,
)
from .paths import PathManager, ScopeNotAvailableError, get_effective_scope, validate_scope_for_write
from .project_utils import get_project_slug
from .provider_loader import get_provider_info, get_provider_models, load_provider_class
from .provider_manager import ConfigureResult, ProviderInfo, ProviderManager, ResetResult
from .provider_sources import (
    DEFAULT_PROVIDER_SOURCES,
    get_effective_provider_sources,
    install_known_providers,
    is_local_path,
    source_from_uri,
)
from .session_spawner import merge_agent_configs, resume_sub_session, spawn_sub_session
from .session_store import SessionStore

__version__ = "0.1.0"

__all__ = [
    # Core path management
    "PathManager",
    "ScopeType",
    "ScopeNotAvailableError",
    "validate_scope_for_write",
    "get_effective_scope",
    # Provider management
    "ProviderManager",
    "ProviderInfo",
    "ConfigureResult",
    "ResetResult",
    # Provider loading
    "load_provider_class",
    "get_provider_info",
    "get_provider_models",
    # Provider sources
    "DEFAULT_PROVIDER_SOURCES",
    "get_effective_provider_sources",
    "install_known_providers",
    "is_local_path",
    "source_from_uri",
    # Module management
    "ModuleManager",
    "ModuleInfo",
    "AddModuleResult",
    "RemoveModuleResult",
    "ModuleType",
    # App settings
    "AppSettings",
    # Effective config
    "EffectiveConfigSummary",
    "get_effective_config_summary",
    # Session management
    "SessionStore",
    "spawn_sub_session",
    "resume_sub_session",
    "merge_agent_configs",
    # Config resolution
    "resolve_app_config",
    "deep_merge",
    "expand_env_vars",
    # Project utilities
    "get_project_slug",
    # Key management
    "KeyManager",
    # Version
    "__version__",
]
