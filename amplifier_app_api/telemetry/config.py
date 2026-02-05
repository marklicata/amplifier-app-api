"""
Telemetry Configuration

Centralized configuration for all telemetry features including
connection settings, sampling, privacy, and performance options.
"""


from pydantic_settings import BaseSettings


class TelemetryConfig(BaseSettings):
    """Telemetry configuration loaded from environment variables."""

    # Connection
    app_insights_connection_string: str | None = None
    enabled: bool = True

    # Application Identity (REQUIRED in all events)
    app_id: str = "amplifier-app-api"
    environment: str = "development"  # dev/staging/production

    # Sampling
    sample_rate: float = 1.0  # 1.0 = 100%, 0.1 = 10%
    sample_rate_errors: float = 1.0  # Always capture errors

    # Privacy
    sanitize_pii: bool = True
    truncate_large_payloads: bool = True
    max_payload_size: int = 10_000  # characters

    # Performance
    flush_interval_seconds: int = 5

    # Development
    enable_dev_logger: bool = True
    dev_logger_max_size_mb: int = 10

    # Request tracking
    track_request_headers: bool = False
    track_response_headers: bool = False
    track_request_body: bool = False  # Privacy risk
    track_response_body: bool = False  # Privacy risk

    model_config = {
        "env_prefix": "TELEMETRY_",
        "env_file": ".env",
        "extra": "ignore",
    }


# Global instance (lazy loaded)
_config: TelemetryConfig | None = None


def get_telemetry_config() -> TelemetryConfig:
    """Get the global telemetry configuration instance."""
    global _config
    if _config is None:
        _config = TelemetryConfig()
    return _config
