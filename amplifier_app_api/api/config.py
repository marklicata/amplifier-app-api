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


@router.post(
    "",
    response_model=ConfigResponse,
    status_code=201,
    summary="Create a new config",
    description="""
Create a new config (complete YAML bundle).

A config contains everything needed to start an Amplifier session:
- Tools, providers, hooks
- Session configuration (orchestrator, context manager)
- Agents, spawn policies
- All includes and dependencies

Configs are reusable - create once, use for multiple sessions.

The YAML content is validated for:
- Valid YAML syntax
- Required section: bundle
- Required field: bundle.name
- Other sections (session, providers, tools) are optional and can be provided via includes

Example minimal config:
```yaml
bundle:
  name: my-config

includes:
  - bundle: foundation

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-5
```
""",
)
async def create_config(
    request: ConfigCreateRequest,
    manager: ConfigManager = Depends(get_config_manager),
) -> ConfigResponse:
    """Create a new config with YAML validation."""
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
