"""
Application Insights Telemetry Tracker

Initializes and configures Azure Application Insights for comprehensive telemetry tracking.
Provides utilities for tracking custom events, metrics, and exceptions.
"""

import logging
from typing import Any

from opencensus.ext.azure import metrics_exporter
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.stats import aggregation as aggregation_module
from opencensus.stats import measure as measure_module
from opencensus.stats import stats as stats_module
from opencensus.stats import view as view_module
from opencensus.tags import tag_map as tag_map_module

from .config import get_telemetry_config
from .context import get_request_context
from .dev_logger import log_dev_event

# Global instance (singleton)
_app_insights_logger: logging.Logger | None = None
_metrics_exporter: metrics_exporter.MetricsExporter | None = None
_stats_recorder = stats_module.stats.stats_recorder


def initialize_telemetry() -> logging.Logger | None:
    """
    Initialize Application Insights telemetry.

    Call this once at application startup.

    Returns:
        Logger instance if successful, None if disabled or connection string missing
    """
    global _app_insights_logger, _metrics_exporter

    # Check if already initialized
    if _app_insights_logger is not None:
        return _app_insights_logger

    # Get configuration
    config = get_telemetry_config()

    if not config.enabled:
        logging.info("[Telemetry] Telemetry disabled by configuration")
        return None

    if not config.app_insights_connection_string:
        logging.warning(
            "[Telemetry] No Application Insights connection string found. Telemetry disabled."
        )
        return None

    try:
        # Set up Azure Log Handler for logging integration
        logger = logging.getLogger("amplifier_telemetry")
        logger.setLevel(logging.INFO)

        # Add Azure handler
        azure_handler = AzureLogHandler(connection_string=config.app_insights_connection_string)

        # Add custom properties to all log entries
        def callback_function(envelope):
            # Add global context properties
            context = get_request_context()
            envelope.data.baseData.properties.update(context)

            # Add app identity
            envelope.data.baseData.properties["app_id"] = config.app_id
            envelope.data.baseData.properties["environment"] = config.environment

            return True

        azure_handler.add_telemetry_processor(callback_function)
        logger.addHandler(azure_handler)

        # Set up metrics exporter
        _metrics_exporter = metrics_exporter.new_metrics_exporter(
            connection_string=config.app_insights_connection_string
        )

        _app_insights_logger = logger

        logging.info("[Telemetry] Application Insights initialized successfully")

        # Track app start
        track_event("app_started", {"app_id": config.app_id, "environment": config.environment})

        return logger

    except Exception as e:
        logging.error(f"[Telemetry] Failed to initialize Application Insights: {e}")
        return None


def get_app_insights() -> logging.Logger | None:
    """
    Get the Application Insights logger instance.

    Returns:
        Logger instance if initialized, None otherwise
    """
    return _app_insights_logger


def track_event(name: str, properties: dict[str, Any] | None = None) -> None:
    """
    Track a custom event.

    Automatically includes request context (request_id, user_id, session_id)
    and app identity (app_id, environment).

    Args:
        name: Event name
        properties: Additional event properties
    """
    config = get_telemetry_config()
    context = get_request_context()

    # Merge properties with context
    merged_properties = {
        **context,
        "app_id": config.app_id,
        "environment": config.environment,
        **(properties or {}),
    }

    # Log to dev logger
    log_dev_event(name, merged_properties)

    # Track to Application Insights
    if _app_insights_logger:
        # Log as structured custom event
        _app_insights_logger.info(
            name,
            extra={
                "custom_dimensions": merged_properties,
            },
        )


def track_metric(name: str, value: float, properties: dict[str, Any] | None = None) -> None:
    """
    Track a custom metric.

    Args:
        name: Metric name
        value: Metric value
        properties: Additional metric properties
    """
    config = get_telemetry_config()
    context = get_request_context()

    # Merge properties
    merged_properties = {
        **context,
        "app_id": config.app_id,
        "environment": config.environment,
        **(properties or {}),
    }

    # Log to dev logger
    log_dev_event("metric", {"metric_name": name, "metric_value": value, **merged_properties})

    # Track to Application Insights
    if _metrics_exporter:
        # Create measure and view
        measure = measure_module.MeasureFloat(name, name, "units")
        view = view_module.View(
            name,
            name,
            [],
            measure,
            aggregation_module.LastValueAggregation(value),
        )
        view_manager = stats_module.stats.view_manager
        view_manager.register_view(view)

        # Record measurement with tags
        mmap = _stats_recorder.new_measurement_map()
        tmap = tag_map_module.TagMap()

        # Add properties as tags (limited to string values)
        for key, val in merged_properties.items():
            if val is not None:
                tmap.insert(key, str(val))

        mmap.measure_float_put(measure, value)
        mmap.record(tmap)


def track_exception(
    exception: Exception, properties: dict[str, Any] | None = None, level: str = "ERROR"
) -> None:
    """
    Track an exception/error.

    Args:
        exception: Exception instance
        properties: Additional error properties
        level: Log level (ERROR, WARNING, INFO)
    """
    config = get_telemetry_config()
    context = get_request_context()

    # Merge properties
    merged_properties = {
        **context,
        "app_id": config.app_id,
        "environment": config.environment,
        "error_type": type(exception).__name__,
        "error_message": str(exception),
        **(properties or {}),
    }

    # Log to dev logger
    log_dev_event("exception", merged_properties)

    # Track to Application Insights
    if _app_insights_logger:
        log_level = getattr(logging, level.upper(), logging.ERROR)
        _app_insights_logger.log(
            log_level,
            f"Exception: {type(exception).__name__}",
            exc_info=exception,
            extra={"custom_dimensions": merged_properties},
        )


def flush_telemetry() -> None:
    """Flush telemetry immediately (useful before application shutdown)."""
    if _app_insights_logger:
        for handler in _app_insights_logger.handlers:
            if hasattr(handler, "flush"):
                handler.flush()
