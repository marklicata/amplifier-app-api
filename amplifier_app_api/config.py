"""Application configuration using pydantic-settings."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Service settings
    service_host: str = Field(default="0.0.0.0", description="Host to bind the service")
    service_port: int = Field(default=8765, description="Port to bind the service")
    service_workers: int = Field(default=4, description="Number of worker processes")
    log_level: str = Field(default="info", description="Logging level")

    # Database - PostgreSQL connection
    database_url: str | None = Field(
        default=None,
        description="Full database connection URL (overrides individual fields)",
    )
    database_user: str = Field(
        default="amplifier_dev",
        description="Database username",
    )
    database_password: str = Field(
        default="dev_password",
        description="Database password",
    )
    database_host: str = Field(
        default="localhost",
        description="Database host",
    )
    database_port: int = Field(
        default=5432,
        description="Database port",
    )
    database_name: str = Field(
        default="amplifier_dev",
        description="Database name",
    )
    database_pool_min_size: int = Field(
        default=10,
        description="Minimum database connection pool size",
    )
    database_pool_max_size: int = Field(
        default=20,
        description="Maximum database connection pool size",
    )
    database_ssl_mode: str = Field(
        default="prefer",
        description="SSL mode: disable, prefer, require",
    )

    # Security
    secret_key: str = Field(
        default="development-secret-key-change-in-production",
        description="Secret key for JWT encoding",
    )
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(
        default=30, description="Access token expiration in minutes"
    )

    # CORS
    allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:8080",
        description="Allowed CORS origins (comma-separated)",
    )

    def get_allowed_origins(self) -> list[str]:
        """Get allowed origins as a list."""
        if isinstance(self.allowed_origins, str):
            return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]
        return self.allowed_origins

    # Amplifier paths
    amplifier_core_path: Path = Field(
        default=Path("../amplifier-core"),
        description="Path to local amplifier-core fork",
    )
    amplifier_foundation_path: Path = Field(
        default=Path("../amplifier-foundation"),
        description="Path to local amplifier-foundation fork",
    )

    # API Keys
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    azure_openai_api_key: str | None = Field(default=None, description="Azure OpenAI API key")
    google_api_key: str | None = Field(default=None, description="Google API key")

    # Session storage
    session_storage_path: Path = Field(
        default=Path("./sessions"), description="Path to session storage"
    )
    max_session_age_days: int = Field(default=30, description="Maximum session age in days")

    # Rate limiting
    rate_limit_requests_per_minute: int = Field(default=60, description="Rate limit per minute")

    # Authentication
    auth_mode: str = Field(
        default="api_key_jwt",
        description="Authentication mode: none, api_key_jwt, jwt_only",
    )
    auth_required: bool = Field(
        default=False,
        description="Require authentication (set to True for production)",
    )
    use_github_auth_in_dev: bool = Field(
        default=True,
        description="Use GitHub CLI (gh) for user_id when auth is disabled (falls back to 'dev-user')",
    )
    api_key_header: str = Field(
        default="X-API-Key", description="Header name for API key authentication"
    )

    # JWT settings
    jwt_algorithm: str = Field(default="RS256", description="JWT algorithm (RS256 for production)")
    jwt_public_key_url: str | None = Field(
        default=None,
        description="URL to fetch JWT public keys (JWKS endpoint)",
    )
    jwt_issuer: str | None = Field(default=None, description="Expected JWT issuer (iss claim)")
    jwt_audience: str | None = Field(default=None, description="Expected JWT audience (aud claim)")

    def get_database_url(self) -> str:
        """
        Get PostgreSQL connection URL.

        If database_url is set, use it directly.
        Otherwise, construct from individual components.
        """
        from urllib.parse import quote_plus

        if self.database_url:
            return self.database_url

        # URL-encode username and password to handle special characters
        user = quote_plus(self.database_user)
        password = quote_plus(self.database_password)

        # Construct PostgreSQL URL from components
        ssl_param = ""
        if self.database_ssl_mode == "require":
            ssl_param = "?sslmode=require"
        elif self.database_ssl_mode == "prefer":
            ssl_param = "?sslmode=prefer"

        return (
            f"postgresql://{user}:{password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}{ssl_param}"
        )

    def get_api_keys(self) -> dict[str, str]:
        """Get all configured API keys."""
        keys = {}
        if self.anthropic_api_key:
            keys["ANTHROPIC_API_KEY"] = self.anthropic_api_key
        if self.openai_api_key:
            keys["OPENAI_API_KEY"] = self.openai_api_key
        if self.azure_openai_api_key:
            keys["AZURE_OPENAI_API_KEY"] = self.azure_openai_api_key
        if self.google_api_key:
            keys["GOOGLE_API_KEY"] = self.google_api_key
        return keys


# Global settings instance
settings = Settings()
