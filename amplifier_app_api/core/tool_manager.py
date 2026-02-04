"""Tool management and invocation."""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ToolManager:
    """Manages tool listing and invocation."""

    def __init__(self):
        """Initialize tool manager."""
        self._cached_bundle_sessions: dict[str, Any] = {}

    async def get_tools_from_bundle(
        self, bundle_name: str, load_bundle_func: Any
    ) -> list[dict[str, Any]]:
        """Get mounted tools from a bundle.

        Args:
            bundle_name: Name of bundle to load
            load_bundle_func: Function to load bundles (from amplifier-foundation)

        Returns:
            List of tool dicts with name, description, and parameters
        """
        logger.info(f"Loading tools from bundle: {bundle_name}")

        # Load and prepare the bundle
        bundle = await load_bundle_func(bundle_name)
        prepared = await bundle.prepare()

        # Create a temporary session to get mounted tools
        session = await prepared.create_session(session_cwd=Path.cwd())

        try:
            # Get mounted tools from coordinator
            tools = session.coordinator.get("tools")
            if not tools:
                return []

            result = []
            for tool_name, tool_instance in tools.items():
                # Get description from tool
                description = "No description"
                if hasattr(tool_instance, "description"):
                    description = tool_instance.description
                elif hasattr(tool_instance, "__doc__") and tool_instance.__doc__:
                    description = tool_instance.__doc__.strip().split("\n")[0]

                # Get parameters schema if available
                parameters = {}
                if hasattr(tool_instance, "parameters_schema"):
                    parameters = tool_instance.parameters_schema
                elif hasattr(tool_instance, "schema"):
                    parameters = tool_instance.schema

                result.append(
                    {
                        "name": tool_name,
                        "description": description,
                        "parameters": parameters,
                        "has_execute": hasattr(tool_instance, "execute"),
                    }
                )

            return sorted(result, key=lambda t: t["name"])

        finally:
            await session.cleanup()

    async def invoke_tool(
        self,
        bundle_name: str,
        tool_name: str,
        parameters: dict[str, Any],
        load_bundle_func: Any,
    ) -> Any:
        """Invoke a tool within a bundle session context.

        Args:
            bundle_name: Bundle determining which tools are available
            tool_name: Name of tool to invoke
            parameters: Parameters to pass to the tool
            load_bundle_func: Function to load bundles

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found or invocation fails
        """
        logger.info(f"Invoking tool '{tool_name}' from bundle '{bundle_name}'")

        # Load and prepare the bundle
        bundle = await load_bundle_func(bundle_name)
        prepared = await bundle.prepare()

        # Create a temporary session
        session = await prepared.create_session(session_cwd=Path.cwd())

        try:
            # Get mounted tools
            tools = session.coordinator.get("tools")
            if not tools:
                raise ValueError("No tools mounted in session")

            # Find the tool
            if tool_name not in tools:
                available = ", ".join(tools.keys())
                raise ValueError(f"Tool '{tool_name}' not found. Available: {available}")

            tool_instance = tools[tool_name]

            # Invoke the tool
            if hasattr(tool_instance, "execute"):
                result = await tool_instance.execute(parameters)
                logger.info(f"Tool '{tool_name}' executed successfully")
                return result
            else:
                raise ValueError(f"Tool '{tool_name}' does not have execute method")

        finally:
            await session.cleanup()
