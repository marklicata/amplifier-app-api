"""Bundle management API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..core import ConfigManager
from ..models import BundleAddRequest, BundleInfo, BundleListResponse
from ..storage import Database, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bundles", tags=["bundles"])


async def get_config_manager(db: Database = Depends(get_db)) -> ConfigManager:
    """Dependency to get config manager."""
    return ConfigManager(db)


@router.get("", response_model=BundleListResponse)
async def list_bundles(
    manager: ConfigManager = Depends(get_config_manager),
) -> BundleListResponse:
    """List all bundles."""
    try:
        bundles = await manager.list_bundles()
        active_bundle = await manager.get_active_bundle()

        bundle_infos = [
            BundleInfo(
                name=name,
                source=config.get("source", ""),
                active=(name == active_bundle),
                description=config.get("description"),
            )
            for name, config in bundles.items()
        ]

        return BundleListResponse(bundles=bundle_infos, active=active_bundle)
    except Exception as e:
        logger.error(f"Error listing bundles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def add_bundle(
    request: BundleAddRequest,
    manager: ConfigManager = Depends(get_config_manager),
) -> dict[str, Any]:
    """Add a new bundle."""
    try:
        # Derive name from source if not provided
        name = request.name
        if not name:
            # Extract name from git URL or path
            if request.source.startswith("git+"):
                name = request.source.split("/")[-1].replace(".git", "")
            else:
                name = request.source.split("/")[-1]

        await manager.add_bundle(
            name=name,
            source=request.source,
            scope=request.scope,
        )

        return {"message": f"Bundle '{name}' added successfully", "name": name}
    except Exception as e:
        logger.error(f"Error adding bundle: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{bundle_name}")
async def get_bundle(
    bundle_name: str,
    manager: ConfigManager = Depends(get_config_manager),
) -> BundleInfo:
    """Get bundle details."""
    bundles = await manager.list_bundles()
    bundle = bundles.get(bundle_name)

    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    active_bundle = await manager.get_active_bundle()

    return BundleInfo(
        name=bundle_name,
        source=bundle.get("source", ""),
        active=(bundle_name == active_bundle),
        description=bundle.get("description"),
    )


@router.delete("/{bundle_name}")
async def remove_bundle(
    bundle_name: str,
    manager: ConfigManager = Depends(get_config_manager),
) -> dict[str, Any]:
    """Remove a bundle."""
    success = await manager.remove_bundle(bundle_name)
    if not success:
        raise HTTPException(status_code=404, detail="Bundle not found")

    return {"message": f"Bundle '{bundle_name}' removed successfully"}


@router.post("/{bundle_name}/activate")
async def activate_bundle(
    bundle_name: str,
    manager: ConfigManager = Depends(get_config_manager),
) -> dict[str, Any]:
    """Set the active bundle."""
    bundles = await manager.list_bundles()
    if bundle_name not in bundles:
        raise HTTPException(status_code=404, detail="Bundle not found")

    await manager.set_active_bundle(bundle_name)
    return {"message": f"Bundle '{bundle_name}' activated"}
