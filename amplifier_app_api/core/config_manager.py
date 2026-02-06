"""Configuration manager for Amplifier configs."""

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import yaml

from ..models import Config, ConfigMetadata
from ..storage import Database
from .config_validator import ConfigValidator

if TYPE_CHECKING:
    from .session_manager import SessionManager

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages Amplifier configurations (complete YAML bundles)."""

    def __init__(self, db: Database, session_manager: "SessionManager | None" = None):
        """Initialize configuration manager.

        Args:
            db: Database instance
            session_manager: Optional SessionManager for cache invalidation
        """
        self.db = db
        self._session_manager = session_manager

    def set_session_manager(self, session_manager: "SessionManager") -> None:
        """Set the session manager for cache invalidation.

        This is called after SessionManager is created to avoid circular dependency.

        Args:
            session_manager: SessionManager instance
        """
        self._session_manager = session_manager

    async def create_config(
        self,
        name: str,
        yaml_content: str,
        description: str | None = None,
        tags: dict[str, str] | None = None,
        validate: bool = True,
    ) -> Config:
        """Create a new config.

        Args:
            name: Human-readable name for the config
            yaml_content: Complete YAML bundle content
            description: Optional description
            tags: Optional tags for categorization
            validate: Whether to validate config structure (default: True)

        Returns:
            Config: The created config

        Raises:
            ValueError: If YAML syntax is invalid
            ConfigValidationError: If config structure is invalid
        """
        config_id = str(uuid.uuid4())

        # Validate YAML syntax
        try:
            parsed = yaml.safe_load(yaml_content)
            if not isinstance(parsed, dict):
                raise ValueError("YAML content must be a dictionary/object, not a scalar value")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML syntax: {e}") from e

        # Validate config structure
        if validate:
            ConfigValidator.validate(parsed)

        config = Config(
            config_id=config_id,
            name=name,
            description=description,
            yaml_content=yaml_content,
            tags=tags or {},
        )

        await self.db.create_config(
            config_id=config_id,
            name=name,
            description=description,
            yaml_content=yaml_content,
            tags=tags or {},
        )

        logger.info(f"Created config: {config_id} ({name})")
        return config

    async def get_config(self, config_id: str) -> Config | None:
        """Get config by ID.

        Args:
            config_id: Config identifier

        Returns:
            Config or None if not found
        """
        data = await self.db.get_config(config_id)
        if not data:
            return None

        return Config(
            config_id=data["config_id"],
            name=data["name"],
            description=data.get("description"),
            yaml_content=data["yaml_content"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            tags=data.get("tags", {}),
        )

    async def update_config(
        self,
        config_id: str,
        name: str | None = None,
        yaml_content: str | None = None,
        description: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> Config | None:
        """Update an existing config.

        Args:
            config_id: Config identifier
            name: Updated name
            yaml_content: Updated YAML content
            description: Updated description
            tags: Updated tags

        Returns:
            Updated Config or None if not found

        Raises:
            ValueError: If YAML is invalid
        """
        config = await self.get_config(config_id)
        if not config:
            return None

        # Validate YAML if provided
        if yaml_content is not None:
            try:
                parsed = yaml.safe_load(yaml_content)
                if not isinstance(parsed, dict):
                    raise ValueError("YAML content must be a dictionary/object, not a scalar value")
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML syntax: {e}") from e

            # Validate config structure
            ConfigValidator.validate(parsed)

        # Update fields (updated_at is handled automatically by database)
        updates: dict[str, Any] = {}
        if name is not None:
            updates["name"] = name
        if yaml_content is not None:
            updates["yaml_content"] = yaml_content
        if description is not None:
            updates["description"] = description
        if tags is not None:
            updates["tags"] = tags

        await self.db.update_config(config_id, **updates)

        # Invalidate bundle cache if YAML content changed
        if yaml_content is not None and self._session_manager:
            self._session_manager.invalidate_config_cache(config_id)
            logger.info(f"Invalidated bundle cache for config: {config_id}")

        logger.info(f"Updated config: {config_id}")
        return await self.get_config(config_id)

    async def delete_config(self, config_id: str) -> bool:
        """Delete a config.

        Args:
            config_id: Config identifier

        Returns:
            True if deleted, False if not found
        """
        config = await self.get_config(config_id)
        if not config:
            return False

        await self.db.delete_config(config_id)
        logger.info(f"Deleted config: {config_id}")
        return True

    async def list_configs(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[list[ConfigMetadata], int]:
        """List all configs.

        Args:
            limit: Maximum number of configs to return
            offset: Offset for pagination

        Returns:
            Tuple of (list of ConfigMetadata, total count)
        """
        configs_data = await self.db.list_configs(limit=limit, offset=offset)
        total = await self.db.count_configs()

        configs = [
            ConfigMetadata(
                config_id=c["config_id"],
                name=c["name"],
                description=c.get("description"),
                created_at=c["created_at"],
                updated_at=c["updated_at"],
                tags=c.get("tags", {}),
            )
            for c in configs_data
        ]

        return configs, total

    # Helper methods for manipulating YAML programmatically

    def parse_yaml(self, yaml_content: str) -> dict[str, Any]:
        """Parse YAML content to dict.

        Args:
            yaml_content: YAML string

        Returns:
            Parsed YAML as dict

        Raises:
            ValueError: If YAML is invalid
        """
        try:
            return yaml.safe_load(yaml_content) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML: {e}") from e

    def dump_yaml(self, data: dict[str, Any]) -> str:
        """Dump dict to YAML string.

        Args:
            data: Dictionary to dump

        Returns:
            YAML string
        """
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    # Bundle management operations

    async def list_bundles(self) -> dict[str, Any]:
        """List all registered bundles.

        Returns:
            Dictionary mapping bundle names to their config (source, description, etc.)
        """
        bundles = await self.db.get_setting("bundles")
        return bundles or {}

    async def get_active_bundle(self) -> str | None:
        """Get the currently active bundle name.

        Returns:
            Active bundle name or None if not set
        """
        return await self.db.get_setting("active_bundle")

    async def add_bundle(
        self,
        name: str,
        source: str,
        scope: str = "global",
    ) -> None:
        """Add a bundle to the registry.

        Args:
            name: Bundle name/alias
            source: Bundle source URI (git URL or path)
            scope: Bundle scope (global, project, local)
        """
        bundles = await self.list_bundles()
        bundles[name] = {
            "source": source,
            "scope": scope,
        }
        await self.db.set_setting("bundles", bundles, scope="global")
        logger.info(f"Added bundle: {name} from {source}")

    async def remove_bundle(self, bundle_name: str) -> bool:
        """Remove a bundle from the registry.

        Args:
            bundle_name: Name of bundle to remove

        Returns:
            True if removed, False if not found
        """
        bundles = await self.list_bundles()
        if bundle_name not in bundles:
            return False

        del bundles[bundle_name]
        await self.db.set_setting("bundles", bundles, scope="global")

        # Clear active bundle if it was the removed one
        active = await self.get_active_bundle()
        if active == bundle_name:
            await self.db.set_setting("active_bundle", None, scope="global")

        logger.info(f"Removed bundle: {bundle_name}")
        return True

    async def set_active_bundle(self, bundle_name: str) -> None:
        """Set the active bundle.

        Args:
            bundle_name: Name of bundle to activate
        """
        await self.db.set_setting("active_bundle", bundle_name, scope="global")
        logger.info(f"Set active bundle: {bundle_name}")

    # Tool registry operations

    async def list_tools_registry(self) -> dict[str, Any]:
        """List all registered tools from global registry.

        Returns:
            Dictionary mapping tool names to their config (source, description, etc.)
        """
        tools = await self.db.get_setting("tools")
        return tools or {}

    async def add_tool(
        self,
        name: str,
        source: str,
        module: str | None = None,
        description: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Add a tool to the global registry.

        Args:
            name: Tool name/alias
            source: Tool source URI (git URL or path)
            module: Tool module identifier (defaults to name)
            description: Optional tool description
            config: Optional tool configuration
        """
        tools = await self.list_tools_registry()
        tools[name] = {
            "source": source,
            "module": module or name,
            "description": description,
            "config": config or {},
        }
        await self.db.set_setting("tools", tools, scope="global")
        logger.info(f"Added tool to registry: {name} from {source}")

    async def get_tool(self, tool_name: str) -> dict[str, Any] | None:
        """Get a tool from the global registry.

        Args:
            tool_name: Name of tool to get

        Returns:
            Tool configuration or None if not found
        """
        tools = await self.list_tools_registry()
        return tools.get(tool_name)

    async def remove_tool(self, tool_name: str) -> bool:
        """Remove a tool from the global registry.

        Args:
            tool_name: Name of tool to remove

        Returns:
            True if removed, False if not found
        """
        tools = await self.list_tools_registry()
        if tool_name not in tools:
            return False

        del tools[tool_name]
        await self.db.set_setting("tools", tools, scope="global")
        logger.info(f"Removed tool from registry: {tool_name}")
        return True

    # Provider registry operations

    async def list_providers_registry(self) -> dict[str, Any]:
        """List all registered providers from global registry.

        Returns:
            Dictionary mapping provider names to their config (source, description, etc.)
        """
        providers = await self.db.get_setting("providers")
        return providers or {}

    async def add_provider_registry(
        self,
        name: str,
        module: str,
        source: str | None = None,
        description: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Add a provider to the global registry.

        Args:
            name: Provider name/alias
            module: Provider module identifier
            source: Provider source URI (git URL or path, optional for installed packages)
            description: Optional provider description
            config: Optional default provider configuration
        """
        providers = await self.list_providers_registry()
        providers[name] = {
            "module": module,
            "source": source,
            "description": description,
            "config": config or {},
        }
        await self.db.set_setting("providers", providers, scope="global")
        logger.info(f"Added provider to registry: {name} (module: {module})")

    async def get_provider_registry(self, provider_name: str) -> dict[str, Any] | None:
        """Get a provider from the global registry.

        Args:
            provider_name: Name of provider to get

        Returns:
            Provider configuration or None if not found
        """
        providers = await self.list_providers_registry()
        return providers.get(provider_name)

    async def remove_provider_registry(self, provider_name: str) -> bool:
        """Remove a provider from the global registry.

        Args:
            provider_name: Name of provider to remove

        Returns:
            True if removed, False if not found
        """
        providers = await self.list_providers_registry()
        if provider_name not in providers:
            return False

        del providers[provider_name]
        await self.db.set_setting("providers", providers, scope="global")
        logger.info(f"Removed provider from registry: {provider_name}")
        return True
