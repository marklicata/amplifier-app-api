"""Session spawning for agent delegation.

Implements sub-session creation with configuration inheritance and overlays.
"""

import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from amplifier_core import AmplifierSession

logger = logging.getLogger(__name__)

SPAN_HEX_LEN = 16
DEFAULT_PARENT_SPAN = "0" * SPAN_HEX_LEN
PARENT_SPAN_PATTERN = re.compile(r"^([0-9a-f]{16})-([0-9a-f]{16})_")
TRACE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def _generate_sub_session_id(
    agent_name: str | None,
    parent_session_id: str | None,
    parent_trace_id: str | None,
) -> str:
    """Generate sanitized sub-session ID using agent suffix and trace lineage.

    Follows W3C Trace Context principles:
    - Parent span ID (16 hex chars) extracted from parent session or trace
    - New child span ID (16 hex chars) for this session
    - Agent name suffix for readability (sanitized for filesystem safety)

    Format: {parent-span}-{child-span}_{agent-name}
    Example: 1234567890abcdef-fedcba0987654321_zen-architect

    This maintains hierarchy tracking while keeping IDs readable and filesystem-safe.
    Agent name is placed at the end for better readability when listing sessions.
    """
    # Sanitize agent name for filesystem safety
    raw_name = (agent_name or "").lower()

    # Replace any non-alphanumeric characters with hyphens
    sanitized = re.sub(r"[^a-z0-9]+", "-", raw_name)
    # Collapse multiple hyphens
    sanitized = re.sub(r"-{2,}", "-", sanitized)
    # Remove leading/trailing hyphens and dots
    sanitized = sanitized.strip("-")
    sanitized = sanitized.lstrip(".")

    # Default to "agent" if empty after sanitization
    if not sanitized:
        sanitized = "agent"

    # Extract parent span ID following W3C Trace Context principles
    parent_span = DEFAULT_PARENT_SPAN
    if parent_session_id:
        # If parent has our format, extract its child span (becomes our parent span)
        match = PARENT_SPAN_PATTERN.match(parent_session_id)
        if match:
            # Extract the child span from parent (second group)
            parent_span = match.group(2)

    # If no parent span found and we have a trace ID, derive parent span from trace
    # Extract middle 16 chars (positions 8-24) from 32-char trace ID
    # This creates a stable parent span ID from the trace without using the full length
    if parent_span == DEFAULT_PARENT_SPAN and parent_trace_id and TRACE_ID_PATTERN.fullmatch(parent_trace_id):
        # Take middle 16 characters (8-24) of the 32-char trace ID
        parent_span = parent_trace_id[8:24]

    # Generate new span ID for this child session
    child_span = uuid.uuid4().hex[:SPAN_HEX_LEN]
    return f"{parent_span}-{child_span}_{sanitized}"


def merge_agent_configs(parent: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Deep merge parent config with agent overlay.

    Uses module list merging for providers, tools, hooks, etc.

    Args:
        parent: Parent session's complete mount plan
        overlay: Agent's partial mount plan (config overlay)

    Returns:
        Merged mount plan for child session
    """
    from amplifier_profiles.merger import merge_profile_dicts

    # Extract agent filter before merge (prevents overwriting parent's agents dict)
    overlay_copy = overlay.copy()
    agent_filter = overlay_copy.pop("agents", None)

    # Standard merge (parent's agents dict preserved since we removed it from overlay)
    result = merge_profile_dicts(parent, overlay_copy)

    # Apply agent filtering (Smart Single Value → filtered dict)
    # Note: "all" and None both mean "inherit parent's agents unchanged" (already in result)
    if agent_filter == "none":
        # Disable all sub-agent delegation
        result["agents"] = {}
    elif isinstance(agent_filter, list):
        # Filter to only specified agent names
        parent_agents = parent.get("agents", {})
        result["agents"] = {k: v for k, v in parent_agents.items() if k in agent_filter}

    return result


async def spawn_sub_session(
    agent_name: str,
    instruction: str,
    parent_session: AmplifierSession,
    agent_configs: dict[str, dict],
    sub_session_id: str | None = None,
    *,
    session_store=None,
    capability_registry_callback=None,
) -> dict:
    """Spawn sub-session with agent configuration overlay.

    Args:
        agent_name: Name of agent from configuration
        instruction: Task for agent to execute
        parent_session: Parent session for inheritance
        agent_configs: Dict of agent configurations
        sub_session_id: Optional explicit ID (generates if None)
        session_store: Optional SessionStore instance (defaults to SessionStore())
        capability_registry_callback: Optional callback(child_session) for registering capabilities

    Returns:
        Dict with "output" (response) and "session_id" (for multi-turn)

    Raises:
        ValueError: If agent not found or config invalid
    """
    # Get agent configuration
    if agent_name not in agent_configs:
        raise ValueError(f"Agent '{agent_name}' not found in configuration")

    agent_config = agent_configs[agent_name]

    # Merge parent config with agent overlay
    merged_config = merge_agent_configs(parent_session.config, agent_config)

    # Generate child session ID using W3C Trace Context span_id pattern
    if not sub_session_id:
        sub_session_id = _generate_sub_session_id(
            agent_name,
            parent_session.session_id,
            getattr(parent_session, "trace_id", None),
        )

    # Create child session with parent_id and inherited UX systems (kernel mechanism)
    child_session = AmplifierSession(
        config=merged_config,
        loader=parent_session.loader,
        session_id=sub_session_id,
        parent_id=parent_session.session_id,  # Links to parent
        approval_system=parent_session.coordinator.approval_system,  # Inherit from parent
        display_system=parent_session.coordinator.display_system,  # Inherit from parent
    )

    # Initialize child session (mounts modules per merged config)
    await child_session.initialize()

    # Register app-layer capabilities if callback provided
    if capability_registry_callback:
        await capability_registry_callback(child_session)

    # Inject agent's system instruction
    system_instruction = agent_config.get("system", {}).get("instruction")
    if system_instruction:
        context = child_session.coordinator.get("context")
        if context and hasattr(context, "add_message"):
            await context.add_message({"role": "system", "content": system_instruction})

    # Execute instruction in child session
    response = await child_session.execute(instruction)

    # Persist state for multi-turn resumption
    if session_store:
        context = child_session.coordinator.get("context")
        transcript = await context.get_messages() if context else []

        # Extract or generate trace_id for W3C Trace Context pattern
        parent_trace_id = getattr(parent_session, "trace_id", parent_session.session_id)

        metadata = {
            "session_id": sub_session_id,
            "parent_id": parent_session.session_id,
            "trace_id": parent_trace_id,
            "agent_name": agent_name,
            "created": datetime.now(UTC).isoformat(),
            "config": merged_config,
            "agent_overlay": agent_config,
            "turn_count": 1,
        }

        session_store.save(sub_session_id, transcript, metadata)
        logger.debug(f"Sub-session {sub_session_id} state persisted")

    # Cleanup child session
    await child_session.cleanup()

    # Return response and session ID for potential multi-turn
    return {"output": response, "session_id": sub_session_id}


async def resume_sub_session(
    sub_session_id: str,
    instruction: str,
    *,
    session_store=None,
    approval_system=None,
    display_system=None,
    capability_registry_callback=None,
) -> dict:
    """Resume existing sub-session for multi-turn engagement.

    Loads previously saved sub-session state, recreates the session with
    full context, executes new instruction, and saves updated state.

    Args:
        sub_session_id: ID of existing sub-session to resume
        instruction: Follow-up instruction to execute
        session_store: Optional SessionStore instance (defaults to SessionStore())
        approval_system: Optional approval system (defaults to creating one)
        display_system: Optional display system (defaults to creating one)
        capability_registry_callback: Optional callback(child_session) for registering capabilities

    Returns:
        Dict with "output" (response) and "session_id" (same ID)

    Raises:
        FileNotFoundError: If session not found in storage
        RuntimeError: If session metadata corrupted or incomplete
        ValueError: If session_id is invalid
    """
    from .session_store import SessionStore

    # Use provided store or create default
    if session_store is None:
        session_store = SessionStore()

    if not session_store.exists(sub_session_id):
        raise FileNotFoundError(
            f"Sub-session '{sub_session_id}' not found. Session may have expired or was never created."
        )

    try:
        transcript, metadata = session_store.load(sub_session_id)
    except Exception as e:
        raise RuntimeError(f"Failed to load sub-session '{sub_session_id}': {str(e)}") from e

    # Extract reconstruction data
    merged_config = metadata.get("config")
    if not merged_config:
        raise RuntimeError(
            f"Corrupted session metadata for '{sub_session_id}'. Cannot reconstruct session without config."
        )

    parent_id = metadata.get("parent_id")
    agent_name = metadata.get("agent_name", "unknown")

    # Recreate child session with same ID and loaded config
    child_session = AmplifierSession(
        config=merged_config,
        loader=None,  # Use default loader
        session_id=sub_session_id,  # REUSE same ID
        parent_id=parent_id,
        approval_system=approval_system,
        display_system=display_system,
    )

    # Initialize session (mounts modules per config)
    await child_session.initialize()

    # Register app-layer capabilities if callback provided
    if capability_registry_callback:
        await capability_registry_callback(child_session)

    # Emit session:resume event for observability
    hooks = child_session.coordinator.get("hooks")
    if hooks:
        await hooks.emit(
            "session:resume",
            {
                "session_id": sub_session_id,
                "parent_id": parent_id,
                "agent_name": agent_name,
                "turn_count": len(transcript) + 1,
            },
        )

    # Restore transcript to context
    context = child_session.coordinator.get("context")
    if context and hasattr(context, "add_message"):
        for message in transcript:
            await context.add_message(message)
    else:
        logger.warning(
            f"Context module does not support add_message() - transcript not restored for session {sub_session_id}"
        )

    # Execute new instruction with full context
    response = await child_session.execute(instruction)

    # Update state for next resumption
    updated_transcript = await context.get_messages() if context else []
    metadata["turn_count"] = len(updated_transcript)
    metadata["last_updated"] = datetime.now(UTC).isoformat()

    session_store.save(sub_session_id, updated_transcript, metadata)
    logger.debug(f"Sub-session {sub_session_id} state updated (turn {metadata['turn_count']})")

    # Cleanup child session
    await child_session.cleanup()

    # Return response and same session ID
    return {"output": response, "session_id": sub_session_id}


__all__ = [
    "spawn_sub_session",
    "resume_sub_session",
    "merge_agent_configs",
]
