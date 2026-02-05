"""
Request Context and Correlation IDs

Manages request-scoped context using contextvars for thread-safe context propagation.
All telemetry events automatically include context from the current request.
"""

import uuid
from contextvars import ContextVar
from typing import Any

# Thread-safe request context storage
_request_context: ContextVar[dict[str, Any]] = ContextVar("request_context", default={})


def generate_correlation_id() -> str:
    """Generate a unique correlation ID for request tracing."""
    return str(uuid.uuid4())


def set_request_context(
    request_id: str,
    user_id: str | None = None,
    session_id: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Set the request context for the current async context.

    This context is automatically included in all telemetry events.

    Args:
        request_id: Correlation ID for request tracing
        user_id: User identifier (required in all events)
        session_id: Session identifier (required in all events)
        **kwargs: Additional context properties
    """
    context = {
        "request_id": request_id,
        "user_id": user_id or "anonymous",
        "session_id": session_id,
        **kwargs,
    }
    _request_context.set(context)


def get_request_context() -> dict[str, Any]:
    """
    Get the current request context.

    Returns:
        Dictionary containing request_id, user_id, session_id, and any additional properties
    """
    return _request_context.get()


def clear_request_context() -> None:
    """Clear the request context for the current async context."""
    _request_context.set({})
