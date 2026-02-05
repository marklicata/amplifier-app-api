"""
Telemetry Event Names

Centralized event name constants following the naming convention:
{domain}_{entity}_{action}

This ensures consistency across the application and makes it easier
to track and analyze service behavior.
"""


class TelemetryEvents:
    """Centralized telemetry event names."""

    # Request lifecycle
    REQUEST_RECEIVED = "request_received"
    REQUEST_COMPLETED = "request_completed"
    REQUEST_FAILED = "request_failed"

    # Session lifecycle
    SESSION_CREATED = "session_created"
    SESSION_RESUMED = "session_resumed"
    SESSION_MESSAGE_SENT = "session_message_sent"
    SESSION_MESSAGE_RECEIVED = "session_message_received"
    SESSION_DELETED = "session_deleted"
    SESSION_EXPIRED = "session_expired"

    # Configuration lifecycle
    CONFIG_CREATED = "config_created"
    CONFIG_UPDATED = "config_updated"
    CONFIG_DELETED = "config_deleted"
    CONFIG_VALIDATED = "config_validated"
    CONFIG_VALIDATION_FAILED = "config_validation_failed"

    # Tool execution
    TOOL_INVOKED = "tool_invoked"
    TOOL_EXECUTION_STARTED = "tool_execution_started"
    TOOL_EXECUTION_COMPLETED = "tool_execution_completed"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"

    # Bundle operations
    BUNDLE_LOADED = "bundle_loaded"
    BUNDLE_VALIDATED = "bundle_validated"
    BUNDLE_VALIDATION_FAILED = "bundle_validation_failed"

    # Health and monitoring
    HEALTH_CHECK_REQUESTED = "health_check_requested"
    HEALTH_CHECK_COMPLETED = "health_check_completed"
    HEALTH_CHECK_FAILED = "health_check_failed"

    # Smoke tests
    SMOKE_TEST_STARTED = "smoke_test_started"
    SMOKE_TEST_COMPLETED = "smoke_test_completed"
    SMOKE_TEST_FAILED = "smoke_test_failed"

    # Error events
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    DATABASE_ERROR = "database_error"
    EXTERNAL_SERVICE_ERROR = "external_service_error"
    TIMEOUT_ERROR = "timeout_error"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"

    # Database operations
    DATABASE_CONNECTION_ACQUIRED = "database_connection_acquired"
    DATABASE_CONNECTION_RELEASED = "database_connection_released"
    DATABASE_CONNECTION_FAILED = "database_connection_failed"

    # Cache operations (if implemented)
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    CACHE_EVICTION = "cache_eviction"

    # Security events
    AUTHENTICATION_ATTEMPTED = "authentication_attempted"
    AUTHENTICATION_SUCCEEDED = "authentication_succeeded"
    AUTHENTICATION_FAILED = "authentication_failed"
    API_KEY_VALIDATED = "api_key_validated"
    API_KEY_REJECTED = "api_key_rejected"
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMIT_TRIGGERED = "rate_limit_triggered"
    RATE_LIMIT_WARNING = "rate_limit_warning"
    SUSPICIOUS_ACTIVITY_DETECTED = "suspicious_activity_detected"

    # Application lifecycle
    APP_STARTED = "app_started"
    APP_STOPPED = "app_stopped"
