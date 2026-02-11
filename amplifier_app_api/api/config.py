"""Configuration API endpoints - CRUD operations for Configs."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

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


def get_user_id(request: Request) -> str | None:
    """Extract user_id from request state (set by auth middleware)."""
    return getattr(request.state, "user_id", None)


@router.post(
    "",
    response_model=ConfigResponse,
    status_code=201,
    summary="Create a new config",
    description="""
Create a new config (complete bundle configuration).

A config contains everything needed to start an Amplifier session.
Configs are reusable - create once, use for multiple sessions.

**Module Sources:** All modules (orchestrator, context, providers, tools) require a `source` field
pointing to their git repository or installation source.

Example:
```json
{
  "name": "my-config",
  "config_data": {
    "bundle": {"name": "my-config", "version": "1.0.0"},
    "includes": [{"bundle": "foundation"}]
  },
  "session": {
    "orchestrator": {
      "module": "loop-streaming",
      "source": "git+https://github.com/microsoft/amplifier-module-loop-streaming@main",
      "config": {}
    },
    "context": {
      "module": "context-simple",
      "source": "git+https://github.com/microsoft/amplifier-module-context-simple@main",
      "config": {}
    }
  },
  "providers": [{
    "module": "provider-anthropic",
    "source": "git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
    "config": {"api_key": "${ANTHROPIC_API_KEY}", "model": "claude-sonnet-4-5"}
  }]
}
```
""",
)
async def create_config(
    request: ConfigCreateRequest,
    http_request: Request,
    manager: ConfigManager = Depends(get_config_manager),
) -> ConfigResponse:
    """Create a new config with validation."""
    try:
        # Extract user_id from request state (set by auth middleware)
        user_id = get_user_id(http_request)

        # Merge optional top-level fields into config_data
        config_data = dict(request.config_data)
        if request.session is not None:
            config_data["session"] = request.session
        if request.includes is not None:
            config_data["includes"] = request.includes
        if request.tools is not None:
            config_data["tools"] = request.tools
        if request.providers is not None:
            config_data["providers"] = request.providers

        config = await manager.create_config(
            name=request.name,
            config_data=config_data,
            description=request.description,
            tags=request.tags,
            user_id=user_id,
        )

        return ConfigResponse(
            config_id=config.config_id,
            name=config.name,
            description=config.description,
            config_data=config.config_data,
            user_id=config.user_id,
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
        config_data=config.config_data,
        user_id=config.user_id,
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
        HTTPException: 404 if not found, 400 if invalid config data, 500 on other errors
    """
    try:
        # Merge optional top-level fields into config_data if provided
        config_data = None
        if request.config_data is not None or any(
            [
                request.session is not None,
                request.includes is not None,
                request.tools is not None,
                request.providers is not None,
            ]
        ):
            # Start with existing config_data or empty dict
            if request.config_data is not None:
                config_data = dict(request.config_data)
            else:
                # If no config_data provided but we have top-level fields, we need to merge with existing
                existing_config = await manager.get_config(config_id)
                if not existing_config:
                    raise HTTPException(status_code=404, detail="Config not found")
                config_data = dict(existing_config.config_data)

            # Merge optional fields
            if request.session is not None:
                config_data["session"] = request.session
            if request.includes is not None:
                config_data["includes"] = request.includes
            if request.tools is not None:
                config_data["tools"] = request.tools
            if request.providers is not None:
                config_data["providers"] = request.providers

        config = await manager.update_config(
            config_id=config_id,
            name=request.name,
            config_data=config_data,
            description=request.description,
            tags=request.tags,
        )

        if not config:
            raise HTTPException(status_code=404, detail="Config not found")

        return ConfigResponse(
            config_id=config.config_id,
            name=config.name,
            description=config.description,
            config_data=config.config_data,
            user_id=config.user_id,
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
