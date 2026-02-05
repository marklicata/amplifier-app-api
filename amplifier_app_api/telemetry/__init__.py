"""
Telemetry Module

Central export point for all telemetry functionality.
Import everything from this single entry point.
"""

from .config import TelemetryConfig, get_telemetry_config
from .context import (
    clear_request_context,
    generate_correlation_id,
    get_request_context,
    set_request_context,
)
from .dev_logger import (
    clear_dev_logs,
    export_dev_logs,
    get_dev_logs,
    is_debug_enabled,
    log_dev_event,
    set_debug,
)
from .events import TelemetryEvents
from .middleware import TelemetryMiddleware
from .tracker import (
    flush_telemetry,
    get_app_insights,
    initialize_telemetry,
    track_event,
    track_exception,
    track_metric,
)

__all__ = [
    # Config
    "TelemetryConfig",
    "get_telemetry_config",
    # Context
    "get_request_context",
    "set_request_context",
    "clear_request_context",
    "generate_correlation_id",
    # Events
    "TelemetryEvents",
    # Tracking
    "initialize_telemetry",
    "get_app_insights",
    "track_event",
    "track_metric",
    "track_exception",
    "flush_telemetry",
    # Dev Logger
    "log_dev_event",
    "export_dev_logs",
    "clear_dev_logs",
    "get_dev_logs",
    "set_debug",
    "is_debug_enabled",
    # Middleware
    "TelemetryMiddleware",
]
