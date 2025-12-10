"""Path management and factory functions for Amplifier applications.

This module centralizes ALL path-related policy decisions for Amplifier applications.
Applications can customize these paths or use sensible defaults.
"""

from pathlib import Path
from typing import TYPE_CHECKING
from typing import Literal

from amplifier_collections import CollectionResolver
from amplifier_config import ConfigManager
from amplifier_config import ConfigPaths
from amplifier_config import Scope

if TYPE_CHECKING:
    from amplifier_profiles import AgentLoader

# Type alias for scope names
ScopeType = Literal["local", "project", "global"]

# Map scope names to Scope enum
_SCOPE_MAP: dict[ScopeType, Scope] = {
    "local": Scope.LOCAL,
    "project": Scope.PROJECT,
    "global": Scope.USER,
}


class PathManager:
    """Manages paths for an Amplifier application.
    
    This class encapsulates path policy decisions, making it easy for applications
    to customize their directory structure while maintaining consistent behavior.
    
    Attributes:
        user_dir: User-wide settings directory (default: ~/.amplifier)
        project_dir: Project-specific directory (default: ./.amplifier)
        bundled_dir: Read-only bundled resources directory
        app_name: Application name (used for user dir if customized)
    """

    def __init__(
        self,
        user_dir: Path | str | None = None,
        project_dir: Path | str | None = None,
        bundled_dir: Path | str | None = None,
        app_name: str = "amplifier",
    ):
        """Initialize path manager.
        
        Args:
            user_dir: User-wide settings directory (default: ~/.{app_name})
            project_dir: Project directory (default: ./.{app_name})
            bundled_dir: Bundled resources (default: package data dir)
            app_name: Application name for default paths
        """
        self.app_name = app_name
        
        # Set user directory
        if user_dir is None:
            self._user_dir = Path.home() / f".{app_name}"
        else:
            self._user_dir = Path(user_dir).expanduser()
        
        # Set project directory
        if project_dir is None:
            self._project_dir = Path(f".{app_name}")
        else:
            self._project_dir = Path(project_dir)
        
        # Set bundled directory
        if bundled_dir is None:
            # Default to package data directory
            package_dir = Path(__file__).parent
            self._bundled_dir = package_dir / "data"
        else:
            self._bundled_dir = Path(bundled_dir)

    @property
    def user_dir(self) -> Path:
        """Get user directory path."""
        return self._user_dir
    
    @property
    def project_dir(self) -> Path:
        """Get project directory path."""
        return self._project_dir
    
    @property
    def bundled_dir(self) -> Path:
        """Get bundled resources directory path."""
        return self._bundled_dir

    def get_config_paths(self) -> ConfigPaths:
        """Get configuration paths for this application.

        Returns:
            ConfigPaths with application conventions:
            - User: {user_dir}/settings.yaml (always enabled)
            - Project: {project_dir}/settings.yaml (disabled when cwd is home)
            - Local: {project_dir}/settings.local.yaml (disabled when cwd is home)

        Note:
            When running from the home directory (~), project and local scopes are
            disabled (set to None) to prevent confusion.
        """
        home = Path.home()
        cwd = Path.cwd()

        # When cwd is home directory, disable project/local scopes
        if cwd == home:
            return ConfigPaths(
                user=self.user_dir / "settings.yaml",
                project=None,
                local=None,
            )

        return ConfigPaths(
            user=self.user_dir / "settings.yaml",
            project=self.project_dir / "settings.yaml",
            local=self.project_dir / "settings.local.yaml",
        )

    def is_running_from_home(self) -> bool:
        """Check if running from the home directory.

        Returns:
            True if cwd is the user's home directory
        """
        return Path.cwd() == Path.home()

    def get_collection_search_paths(self) -> list[Path]:
        """Get collection search paths.

        Search order (highest precedence first):
        1. Project collections ({project_dir}/collections/)
        2. User collections ({user_dir}/collections/)
        3. Bundled collections ({bundled_dir}/collections)

        Returns:
            List of paths to search for collections
        """
        return [
            Path.cwd() / self.project_dir / "collections",  # Project (highest)
            self.user_dir / "collections",  # User
            self.bundled_dir / "collections",  # Bundled (lowest)
        ]

    def get_collection_lock_path(self, local: bool = False) -> Path:
        """Get collection lock path.

        Args:
            local: If True, use project lock; if False, use user lock

        Returns:
            Path to collection lock file
        """
        if local:
            return self.project_dir / "collections.lock"
        return self.user_dir / "collections.lock"

    def get_profile_search_paths(self) -> list[Path]:
        """Get profile search paths using library mechanisms.

        Search order (highest precedence first):
        1. Project profiles ({project_dir}/profiles/)
        2. User profiles ({user_dir}/profiles/)
        3. Collection profiles (via CollectionResolver)
        4. Bundled profiles ({bundled_dir}/profiles)

        Returns:
            List of paths to search for profiles
        """
        from amplifier_collections import discover_collection_resources

        paths = []

        # Project (highest precedence)
        project_profiles = Path.cwd() / self.project_dir / "profiles"
        if project_profiles.exists():
            paths.append(project_profiles)

        # User
        user_profiles = self.user_dir / "profiles"
        if user_profiles.exists():
            paths.append(user_profiles)

        # Collection profiles
        resolver = self.create_collection_resolver()
        for _metadata_name, collection_path in resolver.list_collections():
            resources = discover_collection_resources(collection_path)

            if resources.profiles:
                profile_dir = resources.profiles[0].parent
                if profile_dir not in paths:
                    paths.append(profile_dir)

        # Bundled profiles
        bundled_profiles = self.bundled_dir / "profiles"
        if bundled_profiles.exists():
            paths.append(bundled_profiles)

        return paths

    def get_agent_search_paths(self) -> list[Path]:
        """Get agent search paths using library mechanisms.

        Search order (highest precedence first):
        1. Project agents ({project_dir}/agents/)
        2. User agents ({user_dir}/agents/)
        3. Collection agents (via CollectionResolver)
        4. Bundled agents ({bundled_dir}/agents)

        Returns:
            List of paths to search for agents
        """
        from amplifier_collections import discover_collection_resources

        paths = []

        # Project (highest precedence)
        project_agents = Path.cwd() / self.project_dir / "agents"
        if project_agents.exists():
            paths.append(project_agents)

        # User
        user_agents = self.user_dir / "agents"
        if user_agents.exists():
            paths.append(user_agents)

        # Collection agents
        resolver = self.create_collection_resolver()
        for _metadata_name, collection_path in resolver.list_collections():
            resources = discover_collection_resources(collection_path)

            if resources.agents:
                agent_dir = resources.agents[0].parent
                if agent_dir not in paths:
                    paths.append(agent_dir)

        return paths

    def get_workspace_dir(self) -> Path:
        """Get workspace directory for local modules.

        Returns:
            Path to workspace directory ({project_dir}/modules/)
        """
        return self.project_dir / "modules"

    def get_session_dir(self) -> Path:
        """Get session storage directory.

        Returns:
            Path to session directory ({user_dir}/sessions/)
        """
        return self.user_dir / "sessions"

    def get_keys_file(self) -> Path:
        """Get encrypted keys file path.

        Returns:
            Path to keys file ({user_dir}/keys.enc)
        """
        return self.user_dir / "keys.enc"

    # ===== DEPENDENCY FACTORIES =====

    def create_config_manager(self) -> ConfigManager:
        """Create config manager with path policy injected.

        Returns:
            ConfigManager with application path policy
        """
        return ConfigManager(paths=self.get_config_paths())

    def create_collection_resolver(self) -> CollectionResolver:
        """Create collection resolver with source provider.

        Returns:
            CollectionResolver with search paths and source provider injected
        """
        config = self.create_config_manager()

        # Implement CollectionSourceProvider protocol
        class CollectionSourceProvider:
            """Provides collection source overrides from settings."""

            def get_collection_source(self, collection_name: str) -> str | None:
                """Get collection source override from settings."""
                return config.get_collection_sources().get(collection_name)

        # pyright: ignore[reportCallIssue]
        return CollectionResolver(
            search_paths=self.get_collection_search_paths(),
            source_provider=CollectionSourceProvider(),  # type: ignore[call-arg]
        )

    def create_profile_loader(
        self,
        collection_resolver: CollectionResolver | None = None,
    ):
        """Create profile loader with dependencies.

        Args:
            collection_resolver: Optional collection resolver (creates one if not provided)

        Returns:
            ProfileLoader with paths and protocols injected
        """
        from amplifier_profiles import ProfileLoader
        
        if collection_resolver is None:
            collection_resolver = self.create_collection_resolver()

        from .mention_loading import MentionLoader

        return ProfileLoader(
            search_paths=self.get_profile_search_paths(),
            collection_resolver=collection_resolver,
            mention_loader=MentionLoader(),
        )

    def create_agent_loader(
        self,
        collection_resolver: CollectionResolver | None = None,
    ) -> "AgentLoader":
        """Create agent loader with dependencies.

        Args:
            collection_resolver: Optional collection resolver (creates one if not provided)

        Returns:
            AgentLoader with paths and protocols injected
        """
        from amplifier_profiles import AgentLoader, AgentResolver

        if collection_resolver is None:
            collection_resolver = self.create_collection_resolver()

        from .mention_loading import MentionLoader

        resolver = AgentResolver(
            search_paths=self.get_agent_search_paths(),
            collection_resolver=collection_resolver,
        )

        return AgentLoader(
            resolver=resolver,
            mention_loader=MentionLoader(),
        )

    def create_module_resolver(self):
        """Create module resolver with settings and collection providers.

        Returns:
            StandardModuleSourceResolver with providers injected
        """
        from amplifier_module_resolution import StandardModuleSourceResolver
        
        config = self.create_config_manager()

        # Implement SettingsProviderProtocol
        class SettingsProvider:
            """Provides module sources from settings."""

            def get_module_sources(self) -> dict[str, str]:
                """Get all module sources from settings.

                Merges sources from multiple locations:
                1. settings.sources (explicit source overrides)
                2. settings.modules.providers[] (registered provider modules)
                3. settings.modules.tools[] (registered tool modules)
                4. settings.modules.hooks[] (registered hook modules)
                """
                # Start with explicit source overrides
                sources = dict(config.get_module_sources())

                # Extract sources from registered modules
                merged = config.get_merged_settings()
                modules_section = merged.get("modules", {})

                # Check each module type category
                for category in ["providers", "tools", "hooks", "orchestrators", "contexts"]:
                    module_list = modules_section.get(category, [])
                    if isinstance(module_list, list):
                        for entry in module_list:
                            if isinstance(entry, dict):
                                module_id = entry.get("module")
                                source = entry.get("source")
                                if module_id and source:
                                    sources[module_id] = source

                return sources

            def get_module_source(self, module_id: str) -> str | None:
                """Get module source from settings."""
                return self.get_module_sources().get(module_id)

        # Implement CollectionModuleProviderProtocol
        class CollectionModuleProvider:
            """Provides modules from installed collections."""

            def get_collection_modules(self) -> dict[str, str]:
                """Get module_id -> absolute_path from installed collections."""
                from amplifier_collections import discover_collection_resources

                resolver = self.create_collection_resolver()
                modules = {}

                for _metadata_name, collection_path in resolver.list_collections():
                    resources = discover_collection_resources(collection_path)

                    for module_path in resources.modules:
                        module_name = module_path.name
                        modules[module_name] = str(module_path)

                return modules

        # pyright: ignore[reportCallIssue]
        return StandardModuleSourceResolver(
            settings_provider=SettingsProvider(),
            collection_provider=CollectionModuleProvider(),  # type: ignore[call-arg]
            workspace_dir=self.get_workspace_dir(),
        )


# ===== SCOPE VALIDATION UTILITIES =====


class ScopeNotAvailableError(Exception):
    """Raised when a requested scope is not available."""

    def __init__(self, scope: ScopeType, message: str):
        self.scope = scope
        self.message = message
        super().__init__(message)


def validate_scope_for_write(
    scope: ScopeType,
    config: ConfigManager,
    *,
    allow_fallback: bool = False,
) -> ScopeType:
    """Validate that a scope is available for write operations.

    Args:
        scope: The requested scope ("local", "project", or "global")
        config: ConfigManager instance to check
        allow_fallback: If True, fall back to "global" when scope unavailable

    Returns:
        The validated scope (may be "global" if fallback allowed)

    Raises:
        ScopeNotAvailableError: If scope is not available and fallback not allowed
    """
    scope_enum = _SCOPE_MAP[scope]

    if config.is_scope_available(scope_enum):
        return scope

    # Scope not available
    if allow_fallback:
        return "global"

    # Build helpful error message
    if Path.cwd() == Path.home():
        raise ScopeNotAvailableError(
            scope,
            f"The '{scope}' scope is not available when running from your home directory.\n"
            f"Use --global instead to save to user settings.\n\n"
            f"Tip: Project and local scopes require being in a project directory.",
        )

    raise ScopeNotAvailableError(
        scope,
        f"The '{scope}' scope is not available.\nUse --global instead.",
    )


def get_effective_scope(
    requested_scope: ScopeType | None,
    config: ConfigManager,
    *,
    default_scope: ScopeType = "local",
) -> tuple[ScopeType, bool]:
    """Get the effective scope, handling fallbacks gracefully.

    When no scope is explicitly requested and the default isn't available,
    falls back to "global" scope with a warning.

    Args:
        requested_scope: Explicitly requested scope, or None for default
        config: ConfigManager instance to check
        default_scope: Default scope when none requested

    Returns:
        Tuple of (effective_scope, was_fallback_used)
        - effective_scope: The scope to use
        - was_fallback_used: True if we fell back from the default

    Raises:
        ScopeNotAvailableError: If an explicitly requested scope is not available
    """
    if requested_scope is not None:
        # User explicitly requested a scope - validate without fallback
        return validate_scope_for_write(requested_scope, config, allow_fallback=False), False

    # No explicit request - use default with fallback
    effective = validate_scope_for_write(default_scope, config, allow_fallback=True)
    was_fallback = effective != default_scope
    return effective, was_fallback
