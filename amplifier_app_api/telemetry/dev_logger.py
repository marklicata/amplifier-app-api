"""
Development Logger

Provides local development logging with JSONL export for debugging.
Events are logged to a rotating in-memory buffer with size limits.
"""

import json
from collections import deque
from datetime import datetime
from typing import Any

# Configuration
_debug_enabled = False
_max_events = 1000  # Maximum events to keep in memory
_max_size_bytes = 10 * 1024 * 1024  # 10MB limit

# Event storage (deque for efficient rotation)
_event_buffer: deque[dict[str, Any]] = deque(maxlen=_max_events)
_current_size_bytes = 0


def set_debug(enabled: bool) -> None:
    """Enable or disable debug console output."""
    global _debug_enabled
    _debug_enabled = enabled


def is_debug_enabled() -> bool:
    """Check if debug mode is enabled."""
    return _debug_enabled


def log_dev_event(event_name: str, properties: dict[str, Any]) -> None:
    """
    Log a telemetry event for development/debugging.

    Events are stored in memory with automatic rotation when size limits are reached.
    If debug mode is enabled, events are also printed to console.

    Args:
        event_name: Name of the event
        properties: Event properties dictionary
    """
    global _current_size_bytes

    # Create event record
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_name": event_name,
        "properties": properties,
    }

    # Calculate size
    event_json = json.dumps(event)
    event_size = len(event_json.encode("utf-8"))

    # Check if we need to rotate due to size
    while _current_size_bytes + event_size > _max_size_bytes and len(_event_buffer) > 0:
        # Remove oldest event
        oldest = _event_buffer.popleft()
        oldest_size = len(json.dumps(oldest).encode("utf-8"))
        _current_size_bytes -= oldest_size

    # Add new event
    _event_buffer.append(event)
    _current_size_bytes += event_size

    # Debug output
    if _debug_enabled:
        print(f"[Telemetry] {event_name}: {json.dumps(properties, default=str)}")


def export_dev_logs() -> str:
    """
    Export all logged events as JSONL (JSON Lines) format.

    Returns:
        String containing one JSON object per line
    """
    lines = []
    for event in _event_buffer:
        lines.append(json.dumps(event, default=str))
    return "\n".join(lines)


def clear_dev_logs() -> None:
    """Clear all logged events."""
    global _current_size_bytes
    _event_buffer.clear()
    _current_size_bytes = 0


def get_dev_logs() -> list[dict[str, Any]]:
    """
    Get all logged events as a list.

    Returns:
        List of event dictionaries
    """
    return list(_event_buffer)


def get_dev_log_stats() -> dict[str, Any]:
    """
    Get statistics about the dev logger.

    Returns:
        Dictionary with stats (event_count, size_bytes, max_events, max_size_bytes)
    """
    return {
        "event_count": len(_event_buffer),
        "size_bytes": _current_size_bytes,
        "max_events": _max_events,
        "max_size_bytes": _max_size_bytes,
        "debug_enabled": _debug_enabled,
    }
