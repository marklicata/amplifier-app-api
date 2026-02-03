"""Tool management and invocation API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..core import ConfigManager, ToolManager
from ..core.session_manager import SessionManager
from ..models import ToolInfo, ToolInvokeRequest, ToolListResponse
from ..storage import Database, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools", tags=["tools"])


async def get_config_manager(db: Database = Depends(get_db)) -> ConfigManager:
    """Dependency to get config manager."""
    return ConfigManager(db)


async def get_session_manager(db: Database = Depends(get_db)) -> SessionManager:
    """Dependency to get session manager."""
    return SessionManager(db)


@router.get("", response_model=ToolListResponse)
async def list_tools(
    bundle: str | None = None,
    config_manager: ConfigManager = Depends(get_config_manager),
    session_manager: SessionManager = Depends(get_session_manager),
) -> ToolListResponse:
    """List all available tools from a bundle."""
    try:
        # Determine which bundle to use
        if not bundle:
            bundle = await config_manager.get_active_bundle()
            if not bundle:
                bundle = "foundation"

        logger.info(f"Listing tools from bundle: {bundle}")

        # Get tools using ToolManager
        tool_manager = ToolManager()
        tools_data = await tool_manager.get_tools_from_bundle(
            bundle_name=bundle,
            load_bundle_func=session_manager.load_bundle,
        )

        tools = [
            ToolInfo(
                name=t["name"],
                description=t["description"],
                parameters=t.get("parameters", {}),
            )
            for t in tools_data
        ]

        return ToolListResponse(tools=tools)

    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tool_name}")
async def get_tool_info(
    tool_name: str,
    bundle: str | None = None,
    config_manager: ConfigManager = Depends(get_config_manager),
    session_manager: SessionManager = Depends(get_session_manager),
) -> ToolInfo:
    """Get information about a specific tool."""
    try:
        # Determine which bundle to use
        if not bundle:
            bundle = await config_manager.get_active_bundle()
            if not bundle:
                bundle = "foundation"

        # Get all tools and find the requested one
        tool_manager = ToolManager()
        tools_data = await tool_manager.get_tools_from_bundle(
            bundle_name=bundle,
            load_bundle_func=session_manager.load_bundle,
        )

        # Find the specific tool
        tool_data = next((t for t in tools_data if t["name"] == tool_name), None)
        if not tool_data:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

        return ToolInfo(
            name=tool_data["name"],
            description=tool_data["description"],
            parameters=tool_data.get("parameters", {}),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tool info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/invoke")
async def invoke_tool(
    request: ToolInvokeRequest,
    bundle: str | None = None,
    config_manager: ConfigManager = Depends(get_config_manager),
    session_manager: SessionManager = Depends(get_session_manager),
) -> dict[str, Any]:
    """Invoke a tool with parameters."""
    try:
        # Determine which bundle to use
        if not bundle:
            bundle = await config_manager.get_active_bundle()
            if not bundle:
                bundle = "foundation"

        logger.info(
            f"Invoking tool '{request.tool_name}' from bundle '{bundle}' "
            f"with params: {request.parameters}"
        )

        # Invoke the tool using ToolManager
        tool_manager = ToolManager()
        result = await tool_manager.invoke_tool(
            bundle_name=bundle,
            tool_name=request.tool_name,
            parameters=request.parameters,
            load_bundle_func=session_manager.load_bundle,
        )

        return {
            "tool": request.tool_name,
            "result": result,
            "parameters": request.parameters,
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error invoking tool: {e}")
        raise HTTPException(status_code=500, detail=str(e))
