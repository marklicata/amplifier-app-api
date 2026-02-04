"""Configuration API endpoints - CRUD operations for Configs."""

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from ..core import ConfigManager
from ..models import (
    ConfigCreateRequest,
    ConfigListResponse,
    ConfigResponse,
    ConfigUpdateRequest,
)
from ..storage import Database, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/configs", tags=["configs"])


async def get_config_manager(db: Database = Depends(get_db)) -> ConfigManager:
    """Dependency to get config manager."""
    return ConfigManager(db)


@router.post("", response_model=ConfigResponse, status_code=201)
async def create_config(
    request: ConfigCreateRequest,
    manager: ConfigManager = Depends(get_config_manager),
) -> ConfigResponse:
    """Create a new config.

    Args:
        request: Config creation request with name, YAML content, etc.

    Returns:
        ConfigResponse: The created config

    Raises:
        HTTPException: 400 if YAML is invalid, 500 on other errors
    """
    try:
        config = await manager.create_config(
            name=request.name,
            yaml_content=request.yaml_content,
            description=request.description,
            tags=request.tags,
        )

        return ConfigResponse(
            config_id=config.config_id,
            name=config.name,
            description=config.description,
            yaml_content=config.yaml_content,
            created_at=config.created_at,
            updated_at=config.updated_at,
            tags=config.tags,
            message="Config created successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=ConfigListResponse)
async def list_configs(
    limit: int = 50,
    offset: int = 0,
    manager: ConfigManager = Depends(get_config_manager),
) -> ConfigListResponse:
    """List all configs.

    Args:
        limit: Maximum number of configs to return
        offset: Offset for pagination

    Returns:
        ConfigListResponse: List of config metadata
    """
    try:
        configs, total = await manager.list_configs(limit=limit, offset=offset)

        return ConfigListResponse(configs=configs, total=total)
    except Exception as e:
        logger.error(f"Error listing configs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{config_id}", response_model=ConfigResponse)
async def get_config(
    config_id: str,
    manager: ConfigManager = Depends(get_config_manager),
) -> ConfigResponse:
    """Get config by ID.

    Args:
        config_id: Config identifier

    Returns:
        ConfigResponse: The config details

    Raises:
        HTTPException: 404 if not found, 500 on other errors
    """
    config = await manager.get_config(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    return ConfigResponse(
        config_id=config.config_id,
        name=config.name,
        description=config.description,
        yaml_content=config.yaml_content,
        created_at=config.created_at,
        updated_at=config.updated_at,
        tags=config.tags,
    )


@router.put("/{config_id}", response_model=ConfigResponse)
async def update_config(
    config_id: str,
    request: ConfigUpdateRequest,
    manager: ConfigManager = Depends(get_config_manager),
) -> ConfigResponse:
    """Update an existing config.

    Args:
        config_id: Config identifier
        request: Config update request

    Returns:
        ConfigResponse: The updated config

    Raises:
        HTTPException: 404 if not found, 400 if invalid YAML, 500 on other errors
    """
    try:
        config = await manager.update_config(
            config_id=config_id,
            name=request.name,
            yaml_content=request.yaml_content,
            description=request.description,
            tags=request.tags,
        )

        if not config:
            raise HTTPException(status_code=404, detail="Config not found")

        return ConfigResponse(
            config_id=config.config_id,
            name=config.name,
            description=config.description,
            yaml_content=config.yaml_content,
            created_at=config.created_at,
            updated_at=config.updated_at,
            tags=config.tags,
            message="Config updated successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{config_id}")
async def delete_config(
    config_id: str,
    manager: ConfigManager = Depends(get_config_manager),
) -> dict[str, Any]:
    """Delete a config.

    Args:
        config_id: Config identifier

    Returns:
        Success message

    Raises:
        HTTPException: 404 if not found, 500 on other errors
    """
    try:
        success = await manager.delete_config(config_id)
        if not success:
            raise HTTPException(status_code=404, detail="Config not found")

        return {"message": "Config deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Helper endpoints for programmatic manipulation


@router.post("/{config_id}/tools", response_model=ConfigResponse)
async def add_tool_to_config(
    config_id: str,
    tool_module: str,
    tool_source: str,
    tool_config: dict[str, Any] | None = Body(None),
    manager: ConfigManager = Depends(get_config_manager),
) -> ConfigResponse:
    """Add a tool to a config's YAML.

    Args:
        config_id: Config identifier
        tool_module: Tool module ID
        tool_source: Tool source URI
        tool_config: Optional tool configuration

    Returns:
        ConfigResponse: The updated config
    """
    try:
        config = await manager.add_tool_to_config(
            config_id=config_id,
            module=tool_module,
            source=tool_source,
            config=tool_config,
        )

        if not config:
            raise HTTPException(status_code=404, detail="Config not found")

        return ConfigResponse(
            config_id=config.config_id,
            name=config.name,
            description=config.description,
            yaml_content=config.yaml_content,
            created_at=config.created_at,
            updated_at=config.updated_at,
            tags=config.tags,
            message="Tool added to config successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding tool to config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{config_id}/providers", response_model=ConfigResponse)
async def add_provider_to_config(
    config_id: str,
    provider_module: str,
    provider_source: str | None = None,
    provider_config: dict[str, Any] | None = Body(None),
    manager: ConfigManager = Depends(get_config_manager),
) -> ConfigResponse:
    """Add a provider to a config's YAML.

    Args:
        config_id: Config identifier
        provider_module: Provider module ID
        provider_source: Optional provider source URI
        provider_config: Provider configuration (including api_key)

    Returns:
        ConfigResponse: The updated config
    """
    try:
        config = await manager.add_provider_to_config(
            config_id=config_id,
            module=provider_module,
            source=provider_source,
            config=provider_config,
        )

        if not config:
            raise HTTPException(status_code=404, detail="Config not found")

        return ConfigResponse(
            config_id=config.config_id,
            name=config.name,
            description=config.description,
            yaml_content=config.yaml_content,
            created_at=config.created_at,
            updated_at=config.updated_at,
            tags=config.tags,
            message="Provider added to config successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding provider to config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{config_id}/bundles", response_model=ConfigResponse)
async def merge_bundle_into_config(
    config_id: str,
    bundle_uri: str,
    manager: ConfigManager = Depends(get_config_manager),
) -> ConfigResponse:
    """Add a bundle to the includes section of a config's YAML.

    Args:
        config_id: Config identifier
        bundle_uri: Bundle URI to include

    Returns:
        ConfigResponse: The updated config
    """
    try:
        config = await manager.merge_bundle_into_config(
            config_id=config_id,
            bundle_uri=bundle_uri,
        )

        if not config:
            raise HTTPException(status_code=404, detail="Config not found")

        return ConfigResponse(
            config_id=config.config_id,
            name=config.name,
            description=config.description,
            yaml_content=config.yaml_content,
            created_at=config.created_at,
            updated_at=config.updated_at,
            tags=config.tags,
            message="Bundle merged into config successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error merging bundle into config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
