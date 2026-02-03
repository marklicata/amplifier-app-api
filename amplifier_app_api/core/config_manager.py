"""Configuration manager for providers, bundles, and modules."""

import logging
from typing import Any

from ..storage import Database

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration for providers, bundles, and modules."""

    def __init__(self, db: Database):
        """Initialize configuration manager."""
        self.db = db

    async def get_all_config(self) -> dict[str, Any]:
        """Get all configuration."""
        config = await self.db.get_all_config()
        return {
            "providers": config.get("providers", {}),
            "bundles": config.get("bundles", {}),
            "modules": config.get("modules", {}),
            "active_bundle": config.get("active_bundle"),
            "active_provider": config.get("active_provider"),
        }

    async def update_config(
        self,
        providers: dict[str, Any] | None = None,
        bundles: dict[str, Any] | None = None,
        modules: dict[str, Any] | None = None,
    ) -> None:
        """Update configuration."""
        if providers is not None:
            await self.db.set_config("providers", providers)
        if bundles is not None:
            await self.db.set_config("bundles", bundles)
        if modules is not None:
            await self.db.set_config("modules", modules)

        logger.info("Configuration updated")

    # Provider methods
    async def add_provider(
        self, name: str, api_key: str | None = None, config: dict[str, Any] | None = None
    ) -> None:
        """Add or update a provider configuration."""
        providers = await self.db.get_config("providers") or {}
        providers[name] = {"api_key": api_key, "config": config or {}}
        await self.db.set_config("providers", providers)
        logger.info(f"Added provider: {name}")

    async def get_provider(self, name: str) -> dict[str, Any] | None:
        """Get provider configuration."""
        providers = await self.db.get_config("providers") or {}
        return providers.get(name)

    async def list_providers(self) -> dict[str, Any]:
        """List all configured providers."""
        return await self.db.get_config("providers") or {}

    async def set_active_provider(self, name: str) -> None:
        """Set the active provider."""
        await self.db.set_config("active_provider", name)
        logger.info(f"Set active provider: {name}")

    async def get_active_provider(self) -> str | None:
        """Get the active provider."""
        return await self.db.get_config("active_provider")

    # Bundle methods
    async def add_bundle(self, name: str, source: str, scope: str = "global") -> None:
        """Add a bundle."""
        bundles = await self.db.get_config("bundles") or {}
        bundles[name] = {"source": source, "scope": scope}
        await self.db.set_config("bundles", bundles)
        logger.info(f"Added bundle: {name}")

    async def remove_bundle(self, name: str) -> bool:
        """Remove a bundle."""
        bundles = await self.db.get_config("bundles") or {}
        if name in bundles:
            del bundles[name]
            await self.db.set_config("bundles", bundles)
            logger.info(f"Removed bundle: {name}")
            return True
        return False

    async def list_bundles(self) -> dict[str, Any]:
        """List all bundles."""
        return await self.db.get_config("bundles") or {}

    async def set_active_bundle(self, name: str) -> None:
        """Set the active bundle."""
        await self.db.set_config("active_bundle", name)
        logger.info(f"Set active bundle: {name}")

    async def get_active_bundle(self) -> str | None:
        """Get the active bundle."""
        return await self.db.get_config("active_bundle")

    # Module methods
    async def add_module(self, name: str, source: str, scope: str = "global") -> None:
        """Add a module."""
        modules = await self.db.get_config("modules") or {}
        modules[name] = {"source": source, "scope": scope}
        await self.db.set_config("modules", modules)
        logger.info(f"Added module: {name}")

    async def remove_module(self, name: str) -> bool:
        """Remove a module."""
        modules = await self.db.get_config("modules") or {}
        if name in modules:
            del modules[name]
            await self.db.set_config("modules", modules)
            logger.info(f"Removed module: {name}")
            return True
        return False

    async def list_modules(self) -> dict[str, Any]:
        """List all modules."""
        return await self.db.get_config("modules") or {}
