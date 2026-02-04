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

        # Update fields
        updates: dict[str, Any] = {"updated_at": datetime.now(UTC)}
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

    async def add_tool_to_config(
        self,
        config_id: str,
        module: str,
        source: str,
        config: dict[str, Any] | None = None,
    ) -> Config | None:
        """Add a tool to a config's YAML.

        Args:
            config_id: Config identifier
            module: Tool module ID
            source: Tool source URI
            config: Tool configuration

        Returns:
            Updated Config or None if not found
        """
        cfg = await self.get_config(config_id)
        if not cfg:
            return None

        # Parse YAML
        data = self.parse_yaml(cfg.yaml_content)

        # Add tool
        if "tools" not in data:
            data["tools"] = []

        tool_entry: dict[str, Any] = {"module": module, "source": source}
        if config:
            tool_entry["config"] = config

        data["tools"].append(tool_entry)

        # Update config
        return await self.update_config(config_id, yaml_content=self.dump_yaml(data))

    async def add_provider_to_config(
        self,
        config_id: str,
        module: str,
        source: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> Config | None:
        """Add a provider to a config's YAML.

        Args:
            config_id: Config identifier
            module: Provider module ID
            source: Provider source URI
            config: Provider configuration (including api_key)

        Returns:
            Updated Config or None if not found
        """
        cfg = await self.get_config(config_id)
        if not cfg:
            return None

        # Parse YAML
        data = self.parse_yaml(cfg.yaml_content)

        # Add provider
        if "providers" not in data:
            data["providers"] = []

        provider_entry: dict[str, Any] = {"module": module}
        if source:
            provider_entry["source"] = source
        if config:
            provider_entry["config"] = config

        data["providers"].append(provider_entry)

        # Update config
        return await self.update_config(config_id, yaml_content=self.dump_yaml(data))

    async def merge_bundle_into_config(self, config_id: str, bundle_uri: str) -> Config | None:
        """Add a bundle to the includes section of a config's YAML.

        Args:
            config_id: Config identifier
            bundle_uri: Bundle URI to include

        Returns:
            Updated Config or None if not found
        """
        cfg = await self.get_config(config_id)
        if not cfg:
            return None

        # Parse YAML
        data = self.parse_yaml(cfg.yaml_content)

        # Add to includes
        if "includes" not in data:
            data["includes"] = []

        data["includes"].append({"bundle": bundle_uri})

        # Update config
        return await self.update_config(config_id, yaml_content=self.dump_yaml(data))
