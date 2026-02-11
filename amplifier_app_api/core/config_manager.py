"""Configuration manager for Amplifier configs."""

import json
import logging
import os
import uuid
from typing import TYPE_CHECKING, Any

from amplifier_foundation import Bundle  # type: ignore[import-not-found]

from ..models import Config, ConfigMetadata
from ..storage import Database
from .secrets_encryption import ConfigEncryption

if TYPE_CHECKING:
    from .session_manager import SessionManager

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages Amplifier configurations (complete bundles)."""

    def __init__(self, db: Database, session_manager: "SessionManager | None" = None):
        """Initialize configuration manager.

        Args:
            db: Database instance
            session_manager: Optional SessionManager for cache invalidation
        """
        self.db = db
        self._session_manager = session_manager

        # Initialize encryption if key is available
        self._encryption: ConfigEncryption | None = None
        encryption_key = os.environ.get("CONFIG_ENCRYPTION_KEY")
        if encryption_key:
            try:
                self._encryption = ConfigEncryption(encryption_key)
                logger.info("Config encryption enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize config encryption: {e}")
        else:
            logger.warning("CONFIG_ENCRYPTION_KEY not set - configs will be stored in plain text")

    def validate_config(self, config_dict: dict[str, Any]) -> None:
        """Validate config structure and required fields.

        Args:
            config_dict: Config as dict

        Raises:
            ValueError: If validation fails
        """

        try:
            bundle = Bundle.from_dict(config_dict)  # This will raise if the config is invalid
            if bundle is not None and type(bundle) is Bundle:
                logger.debug("Config validation successful")
        except ValueError as e:
            raise ValueError(f"Config validation error: {e}") from e

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
        config_data: dict[str, Any],
        description: str | None = None,
        tags: dict[str, str] | None = None,
        user_id: str | None = None,
        validate: bool = True,
    ) -> Config:
        """Create a new config.

        Args:
            name: Human-readable name for the config
            config_data: Complete bundle configuration as dict
            description: Optional description
            tags: Optional tags for categorization
            user_id: Optional user ID who owns this config
            validate: Whether to validate config structure (default: True)

        Returns:
            Config: The created config

        Raises:
            ValueError: If config structure is invalid
        """
        config_id = str(uuid.uuid4())

        # Validate that config_data is a dict
        if not isinstance(config_data, dict):
            raise ValueError("config_data must be a dictionary/object, not a scalar value")

        # Validate config structure
        if validate:
            self.validate_config(config_data)

        # Encrypt sensitive fields before storage
        config_to_store = config_data
        if self._encryption:
            config_to_store = self._encryption.encrypt_config(config_data)
            logger.debug("Encrypted sensitive fields in config")

        # Serialize to JSON for storage
        config_json = json.dumps(config_to_store)

        config = Config(
            config_id=config_id,
            name=name,
            description=description,
            config_data=config_data,
            user_id=user_id,
            tags=tags or {},
        )

        await self.db.create_config(
            config_id=config_id,
            name=name,
            description=description,
            config_json=config_json,
            user_id=user_id,
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

        # Parse JSON string back to dict
        config_data = json.loads(data["config_json"])

        # Decrypt sensitive fields after retrieval
        if self._encryption:
            config_data = self._encryption.decrypt_config(config_data)
            logger.debug("Decrypted sensitive fields in config")

        return Config(
            config_id=data["config_id"],
            name=data["name"],
            description=data.get("description"),
            config_data=config_data,
            user_id=data.get("user_id"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            tags=data.get("tags", {}),
        )

    async def update_config(
        self,
        config_id: str,
        name: str | None = None,
        config_data: dict[str, Any] | None = None,
        description: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> Config | None:
        """Update an existing config.

        Args:
            config_id: Config identifier
            name: Updated name
            config_data: Updated config data
            description: Updated description
            tags: Updated tags

        Returns:
            Updated Config or None if not found

        Raises:
            ValueError: If config_data is invalid
        """
        config = await self.get_config(config_id)
        if not config:
            return None

        # Validate config_data if provided
        if config_data is not None:
            if not isinstance(config_data, dict):
                raise ValueError("config_data must be a dictionary/object, not a scalar value")

            # Validate config structure
            self.validate_config(config_data)

        # Update fields (updated_at is handled automatically by database)
        updates: dict[str, Any] = {}
        if name is not None:
            updates["name"] = name
        if config_data is not None:
            # Encrypt sensitive fields before storage
            config_to_store = config_data
            if self._encryption:
                config_to_store = self._encryption.encrypt_config(config_data)
                logger.debug("Encrypted sensitive fields in updated config")
            updates["config_json"] = json.dumps(config_to_store)
        if description is not None:
            updates["description"] = description
        if tags is not None:
            updates["tags"] = tags

        await self.db.update_config(config_id, **updates)

        # Invalidate bundle cache if config data changed
        if config_data is not None and self._session_manager:
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
                user_id=c.get("user_id"),
                created_at=c["created_at"],
                updated_at=c["updated_at"],
                tags=c.get("tags", {}),
            )
            for c in configs_data
        ]

        return configs, total

    # Helper methods for manipulating config data programmatically

    def parse_json(self, json_content: str) -> dict[str, Any]:
        """Parse JSON content to dict.

        Args:
            json_content: JSON string

        Returns:
            Parsed JSON as dict

        Raises:
            ValueError: If JSON is invalid
        """
        try:
            return json.loads(json_content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e

    def dump_json(self, data: dict[str, Any]) -> str:
        """Dump dict to JSON string.

        Args:
            data: Dictionary to dump

        Returns:
            JSON string
        """
        return json.dumps(data, indent=2)

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
