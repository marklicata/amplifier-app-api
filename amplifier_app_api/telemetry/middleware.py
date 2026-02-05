"""
Telemetry Middleware for FastAPI

Automatically tracks all HTTP requests with timing, status codes, and exceptions.
Injects correlation IDs and context for request tracing.
"""

import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .context import clear_request_context, generate_correlation_id, set_request_context
from .events import TelemetryEvents
from .tracker import track_event, track_exception


class TelemetryMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for automatic request telemetry tracking.

    Captures:
    - Request received/completed/failed events
    - Request duration
    - Status codes
    - Request/response sizes
    - Exceptions

    Automatically injects:
    - request_id (correlation ID)
    - user_id (from request state if available)
    - session_id (from request headers or state if available)
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and track telemetry."""
        start_time = time.time()

        # Generate correlation ID
        request_id = generate_correlation_id()

        # Extract user_id from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)

        # Extract session_id from headers or state
        session_id = request.headers.get("X-Session-ID") or getattr(
            request.state, "session_id", None
        )

        # Set request context for this request
        set_request_context(
            request_id=request_id,
            user_id=user_id,
            session_id=session_id,
        )

        # Store in request state for downstream access
        request.state.request_id = request_id
        request.state.start_time = start_time

        try:
            # Track request received
            track_event(
                TelemetryEvents.REQUEST_RECEIVED,
                {
                    "endpoint": request.url.path,
                    "method": request.method,
                },
            )

            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Get request/response sizes
            request_size = int(request.headers.get("content-length", 0))
            response_size = int(response.headers.get("content-length", 0))

            # Track request completed
            track_event(
                TelemetryEvents.REQUEST_COMPLETED,
                {
                    "endpoint": request.url.path,
                    "method": request.method,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "request_size_bytes": request_size,
                    "response_size_bytes": response_size,
                },
            )

            # Add correlation ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Track request failed
            track_exception(
                e,
                {
                    "endpoint": request.url.path,
                    "method": request.method,
                    "duration_ms": duration_ms,
                },
            )

            track_event(
                TelemetryEvents.REQUEST_FAILED,
                {
                    "endpoint": request.url.path,
                    "method": request.method,
                    "duration_ms": duration_ms,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )

            # Re-raise the exception
            raise

        finally:
            # Clear request context
            clear_request_context()
