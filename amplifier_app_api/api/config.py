"""Configuration management API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..core import ConfigManager
from ..models import ConfigResponse, ConfigUpdateRequest, ProviderConfigRequest, ProviderInfo
from ..storage import Database, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["configuration"])


async def get_config_manager(db: Database = Depends(get_db)) -> ConfigManager:
    """Dependency to get config manager."""
    return ConfigManager(db)


@router.get("", response_model=ConfigResponse)
async def get_config(
    manager: ConfigManager = Depends(get_config_manager),
) -> ConfigResponse:
    """Get all configuration."""
    try:
        config = await manager.get_all_config()
        return ConfigResponse(**config)
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def update_config(
    request: ConfigUpdateRequest,
    manager: ConfigManager = Depends(get_config_manager),
) -> dict[str, Any]:
    """Update configuration."""
    try:
        await manager.update_config(
            providers=request.providers,
            bundles=request.bundles,
            modules=request.modules,
        )
        return {"message": "Configuration updated successfully"}
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Provider endpoints
@router.get("/providers", response_model=list[ProviderInfo])
async def list_providers(
    manager: ConfigManager = Depends(get_config_manager),
) -> list[ProviderInfo]:
    """List all configured providers."""
    try:
        providers = await manager.list_providers()

        return [
            ProviderInfo(
                name=name,
                configured=True,
                models=config.get("config", {}).get("models", []),
            )
            for name, config in providers.items()
        ]
    except Exception as e:
        logger.error(f"Error listing providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/providers")
async def add_provider(
    request: ProviderConfigRequest,
    manager: ConfigManager = Depends(get_config_manager),
) -> dict[str, Any]:
    """Add or update a provider configuration."""
    try:
        await manager.add_provider(
            name=request.provider,
            api_key=request.api_key,
            config=request.config,
        )
        return {"message": f"Provider '{request.provider}' configured successfully"}
    except Exception as e:
        logger.error(f"Error adding provider: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers/{provider_name}")
async def get_provider(
    provider_name: str,
    manager: ConfigManager = Depends(get_config_manager),
) -> dict[str, Any]:
    """Get provider configuration."""
    provider = await manager.get_provider(provider_name)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Don't return API key
    config = provider.get("config", {})
    return {"name": provider_name, "configured": True, "config": config}


@router.post("/providers/{provider_name}/activate")
async def activate_provider(
    provider_name: str,
    manager: ConfigManager = Depends(get_config_manager),
) -> dict[str, Any]:
    """Set the active provider."""
    provider = await manager.get_provider(provider_name)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    await manager.set_active_provider(provider_name)
    return {"message": f"Provider '{provider_name}' activated"}


@router.get("/providers/current")
async def get_current_provider(
    manager: ConfigManager = Depends(get_config_manager),
) -> dict[str, Any]:
    """Get the currently active provider."""
    active = await manager.get_active_provider()
    if not active:
        raise HTTPException(status_code=404, detail="No active provider set")

    return {"provider": active}
