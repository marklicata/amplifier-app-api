"""Provider registry API endpoints.

Manages the global provider registry for registering and discovering
LLM providers (Anthropic, OpenAI, Azure, etc.).
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..core import ConfigManager
from ..storage import Database, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/providers", tags=["providers"])


async def get_config_manager(db: Database = Depends(get_db)) -> ConfigManager:
    """Dependency to get config manager."""
    return ConfigManager(db)


@router.post("", status_code=201)
async def register_provider(
    name: str,
    module: str,
    source: str | None = None,
    description: str | None = None,
    config: dict[str, Any] | None = None,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> dict[str, Any]:
    """Register a provider in the global provider registry.

    This allows you to register providers that can be referenced by name
    when adding them to configs.

    Args:
        name: Provider name/alias for the registry
        module: Provider module identifier (e.g., "provider-anthropic", "provider-openai")
        source: Provider source URI (git URL or omit for installed packages)
        description: Optional provider description
        config: Optional default provider configuration (api_key, model, etc.)

    Example:
        ```json
        {
          "name": "anthropic-prod",
          "module": "provider-anthropic",
          "source": "git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
          "description": "Production Anthropic provider",
          "config": {
            "default_model": "claude-sonnet-4-5-20250929",
            "priority": 1
          }
        }
        ```
    """
    try:
        await config_manager.add_provider_registry(
            name=name,
            module=module,
            source=source,
            description=description,
            config=config,
        )
        return {
            "message": f"Provider '{name}' registered successfully",
            "name": name,
            "module": module,
        }
    except Exception as e:
        logger.error(f"Error registering provider: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_providers(
    config_manager: ConfigManager = Depends(get_config_manager),
) -> dict[str, Any]:
    """List all registered providers from global registry.

    Returns:
        Dictionary mapping provider names to their configuration.

    Example response:
        ```json
        {
          "anthropic-prod": {
            "module": "provider-anthropic",
            "source": "git+https://...",
            "description": "Production Anthropic provider",
            "config": {"default_model": "claude-sonnet-4-5-20250929"}
          },
          "openai-dev": {
            "module": "provider-openai",
            "source": null,
            "description": "Development OpenAI provider",
            "config": {"model": "gpt-4"}
          }
        }
        ```
    """
    try:
        providers = await config_manager.list_providers_registry()
        return providers
    except Exception as e:
        logger.error(f"Error listing providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{provider_name}")
async def get_provider(
    provider_name: str,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> dict[str, Any]:
    """Get information about a specific provider from the global registry.

    Args:
        provider_name: Name of the provider to retrieve

    Returns:
        Provider configuration including module, source, description, and config.

    Example response:
        ```json
        {
          "name": "anthropic-prod",
          "module": "provider-anthropic",
          "source": "git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
          "description": "Production Anthropic provider",
          "config": {
            "default_model": "claude-sonnet-4-5-20250929",
            "priority": 1
          }
        }
        ```
    """
    try:
        provider_config = await config_manager.get_provider_registry(provider_name)
        if not provider_config:
            raise HTTPException(
                status_code=404, detail=f"Provider '{provider_name}' not found in registry"
            )

        return {
            "name": provider_name,
            "module": provider_config.get("module"),
            "source": provider_config.get("source"),
            "description": provider_config.get("description", ""),
            "config": provider_config.get("config", {}),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting provider: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{provider_name}")
async def remove_provider(
    provider_name: str,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> dict[str, Any]:
    """Remove a provider from the global registry.

    Args:
        provider_name: Name of the provider to remove

    Returns:
        Success message confirming removal.
    """
    try:
        success = await config_manager.remove_provider_registry(provider_name)
        if not success:
            raise HTTPException(
                status_code=404, detail=f"Provider '{provider_name}' not found in registry"
            )
        return {"message": f"Provider '{provider_name}' removed from registry successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing provider: {e}")
        raise HTTPException(status_code=500, detail=str(e))
