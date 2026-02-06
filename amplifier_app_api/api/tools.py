"""Tool management and invocation API endpoints.

This module provides both:
1. Global tool registry management (register/list/delete tools)
2. Bundle inspection (list tools from a specific bundle)
3. Tool invocation
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

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


@router.post("", status_code=201)
async def register_tool(
    name: str,
    source: str,
    module: str | None = None,
    description: str | None = None,
    config: dict[str, Any] | None = None,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> dict[str, Any]:
    """Register a tool in the global tool registry.

    This allows you to register tools that can be referenced by name
    when adding them to configs.

    Args:
        name: Tool name/alias for the registry
        source: Tool source URI (git URL, registry name, or local path)
        module: Tool module identifier (defaults to name)
        description: Optional tool description
        config: Optional default tool configuration
    """
    try:
        await config_manager.add_tool(
            name=name,
            source=source,
            module=module,
            description=description,
            config=config,
        )
        return {
            "message": f"Tool '{name}' registered successfully",
            "name": name,
            "source": source,
        }
    except Exception as e:
        logger.error(f"Error registering tool: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=ToolListResponse)
async def list_tools(
    bundle: str | None = Query(None, description="Bundle name to inspect tools from"),
    from_registry: bool = Query(False, description="List from global registry instead of bundle"),
    config_manager: ConfigManager = Depends(get_config_manager),
    session_manager: SessionManager = Depends(get_session_manager),
) -> ToolListResponse:
    """List tools from global registry or from a specific bundle.

    Two modes:
    1. Registry mode (from_registry=true): List all registered tools from global registry
    2. Bundle inspection mode (bundle=X): List tools from a specific bundle

    If neither parameter is provided, defaults to bundle inspection with active bundle.
    """
    try:
        if from_registry:
            # List from global registry
            tools_dict = await config_manager.list_tools_registry()
            tools = [
                ToolInfo(
                    name=name,
                    description=config.get("description", ""),
                    parameters={},  # Registry doesn't store full parameters
                )
                for name, config in tools_dict.items()
            ]
            return ToolListResponse(tools=tools)

        # Bundle inspection mode
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
    bundle: str | None = Query(None, description="Bundle name to inspect tool from"),
    from_registry: bool = Query(False, description="Get from global registry instead of bundle"),
    config_manager: ConfigManager = Depends(get_config_manager),
    session_manager: SessionManager = Depends(get_session_manager),
) -> ToolInfo | dict[str, Any]:
    """Get information about a specific tool from registry or bundle.

    Two modes:
    1. Registry mode (from_registry=true): Get tool from global registry
    2. Bundle inspection mode (bundle=X): Get tool from a specific bundle
    """
    try:
        if from_registry:
            # Get from global registry
            tool_config = await config_manager.get_tool(tool_name)
            if not tool_config:
                raise HTTPException(
                    status_code=404, detail=f"Tool '{tool_name}' not found in registry"
                )
            return {
                "name": tool_name,
                "source": tool_config.get("source"),
                "module": tool_config.get("module"),
                "description": tool_config.get("description", ""),
                "config": tool_config.get("config", {}),
            }

        # Bundle inspection mode
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
            raise HTTPException(
                status_code=404, detail=f"Tool '{tool_name}' not found in bundle '{bundle}'"
            )

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


@router.delete("/{tool_name}")
async def remove_tool(
    tool_name: str,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> dict[str, Any]:
    """Remove a tool from the global registry."""
    try:
        success = await config_manager.remove_tool(tool_name)
        if not success:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found in registry")
        return {"message": f"Tool '{tool_name}' removed from registry successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing tool: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/invoke")
async def invoke_tool(
    request: ToolInvokeRequest,
    config_manager: ConfigManager = Depends(get_config_manager),
    session_manager: SessionManager = Depends(get_session_manager),
) -> dict[str, Any]:
    """Invoke a tool with parameters."""
    try:
        # Determine which bundle to use
        # Priority: request.bundle_name > active bundle > foundation
        bundle = request.bundle_name
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
