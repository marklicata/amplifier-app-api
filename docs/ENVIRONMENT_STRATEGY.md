# Environment Strategy: Dev/Test/Prod Database Instances

## Overview

This document outlines the strategy for managing separate PostgreSQL database instances for development, testing, and production environments.

## Environment Architecture

### Recommended Setup

```
┌─────────────────────────────────────────────────────────────┐
│  Development Environment (Local)                            │
│  ┌────────────────┐                                         │
│  │ Local Dev      │──► Local PostgreSQL (Docker)            │
│  │ (your machine) │    Port: 5432                           │
│  └────────────────┘    Database: amplifier_dev              │
│                        User: amplifier_dev                  │
│                        No Azure credentials needed          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Test/Staging Environment (Azure)                           │
│  ┌────────────────┐                                         │
│  │ CI/CD Pipeline │──► Azure PostgreSQL Flexible Server     │
│  │ GitHub Actions │    Name: amplifier-db-test              │
│  └────────────────┘    Tier: Burstable B1ms (~$30/mo)       │
│                        Database: amplifier_test             │
│                        Firewall: GitHub Action IPs          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Production Environment (Azure)                              │
│  ┌────────────────┐                                         │
│  │ Azure App      │──► Azure PostgreSQL Flexible Server     │
│  │ Service        │    Name: amplifier-db-prod              │
│  └────────────────┘    Tier: Burstable B2s (~$60/mo)        │
│         │              Database: amplifier_prod             │
│         │              High Availability: Zone-redundant    │
│         │              Backup: 14 days retention            │
│         └──► Azure Key Vault (kv-amplifier-prod)            │
│                Connection strings, secrets                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Configuration Strategy

### Approach: Environment-Based Configuration

Use environment variables with `.env` files per environment:

```
.env.development    # Local development (git ignored)
.env.test          # Test/CI environment (git ignored)
.env.production    # Production secrets (Azure Key Vault, not in repo)
.env.example       # Template for all environments (git tracked)
```

### Configuration Priority

```
1. Environment variables (highest priority)
2. .env.{ENVIRONMENT} file
3. .env file
4. Default values in Settings class (lowest priority)
```

---

## Environment-Specific Configurations

### Development (.env.development)

```bash
# Environment
ENVIRONMENT=development

# Database - Local PostgreSQL in Docker
DATABASE_URL=postgresql+asyncpg://amplifier_dev:dev_password@localhost:5432/amplifier_dev

# Security (weak keys OK for local)
SECRET_KEY=development-secret-key-not-for-production
AUTH_REQUIRED=false

# CORS (allow local frontends)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:8080

# Telemetry
TELEMETRY_ENABLED=true
TELEMETRY_ENVIRONMENT=development
TELEMETRY_ENABLE_DEV_LOGGER=true
TELEMETRY_APP_INSIGHTS_CONNECTION_STRING=  # Empty - use dev logger

# Rate Limiting (relaxed)
RATE_LIMIT_REQUESTS_PER_MINUTE=1000
```

### Test/Staging (.env.test)

```bash
# Environment
ENVIRONMENT=test

# Database - Azure PostgreSQL Test Instance
DATABASE_URL=postgresql+asyncpg://amplifier_admin@amplifier-db-test:${POSTGRES_PASSWORD}@amplifier-db-test.postgres.database.azure.com:5432/amplifier_test?ssl=require

# Security (from CI secrets)
SECRET_KEY=${TEST_SECRET_KEY}
AUTH_REQUIRED=true

# CORS (test frontend)
ALLOWED_ORIGINS=https://test-app.azurewebsites.net

# Telemetry
TELEMETRY_ENABLED=true
TELEMETRY_ENVIRONMENT=test
TELEMETRY_APP_INSIGHTS_CONNECTION_STRING=${TEST_APP_INSIGHTS_CONNECTION_STRING}

# Rate Limiting (realistic)
RATE_LIMIT_REQUESTS_PER_MINUTE=100
```

### Production (.env.production)

```bash
# Environment
ENVIRONMENT=production

# Database - Loaded from Azure Key Vault (not hardcoded)
# App uses managed identity to fetch from Key Vault
AZURE_KEYVAULT_NAME=kv-amplifier-prod

# Security
SECRET_KEY=  # Loaded from Key Vault
AUTH_REQUIRED=true

# CORS (production frontend only)
ALLOWED_ORIGINS=https://app.yourdomain.com

# Telemetry
TELEMETRY_ENABLED=true
TELEMETRY_ENVIRONMENT=production
TELEMETRY_APP_INSIGHTS_CONNECTION_STRING=  # Loaded from Key Vault
TELEMETRY_SAMPLE_RATE=0.1  # Sample 10% in prod

# Rate Limiting (strict)
RATE_LIMIT_REQUESTS_PER_MINUTE=60
```

---

## Docker Compose Setup for Local Development

### docker-compose.dev.yml

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: amplifier-postgres-dev
    environment:
      POSTGRES_USER: amplifier_dev
      POSTGRES_PASSWORD: dev_password
      POSTGRES_DB: amplifier_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_dev_data:/var/lib/postgresql/data
      - ./scripts/init-dev-db.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U amplifier_dev"]
      interval: 5s
      timeout: 5s
      retries: 5

  api:
    build: .
    container_name: amplifier-api-dev
    env_file:
      - .env.development
    ports:
      - "8765:8765"
    volumes:
      - .:/app
      - ./sessions:/app/sessions
    depends_on:
      postgres:
        condition: service_healthy
    command: uvicorn amplifier_app_api.main:app --host 0.0.0.0 --port 8765 --reload

volumes:
  postgres_dev_data:
```

### scripts/init-dev-db.sql

```sql
-- Development database initialization
-- This runs once when the container is first created

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create helper function for updated_at triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Schema will be created by application on first run
-- This is just for extensions and helper functions
```

---

## Updated Settings Class

### amplifier_app_api/config.py

```python
"""Application configuration using pydantic-settings."""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        # Load from .env.{ENVIRONMENT} first, then .env
        env_file=[
            f".env.{os.getenv('ENVIRONMENT', 'development')}",
            ".env",
        ],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: str = Field(
        default="development",
        description="Environment: development, test, staging, production",
    )

    # Service settings
    service_host: str = Field(default="0.0.0.0", description="Host to bind the service")
    service_port: int = Field(default=8765, description="Port to bind the service")
    service_workers: int = Field(default=4, description="Number of worker processes")
    log_level: str = Field(default="info", description="Logging level")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://amplifier_dev:dev_password@localhost:5432/amplifier_dev",
        description="Database connection URL",
    )
    database_pool_min_size: int = Field(
        default=10, description="Minimum database connection pool size"
    )
    database_pool_max_size: int = Field(
        default=20, description="Maximum database connection pool size"
    )

    # Azure Key Vault (production only)
    azure_keyvault_name: Optional[str] = Field(
        default=None, description="Azure Key Vault name for production secrets"
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
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    azure_openai_api_key: Optional[str] = Field(default=None, description="Azure OpenAI API key")
    google_api_key: Optional[str] = Field(default=None, description="Google API key")

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
    api_key_header: str = Field(
        default="X-API-Key", description="Header name for API key authentication"
    )

    # JWT settings
    jwt_algorithm: str = Field(default="RS256", description="JWT algorithm (RS256 for production)")
    jwt_public_key_url: Optional[str] = Field(
        default=None,
        description="URL to fetch JWT public keys (JWKS endpoint)",
    )
    jwt_issuer: Optional[str] = Field(default=None, description="Expected JWT issuer (iss claim)")
    jwt_audience: Optional[str] = Field(default=None, description="Expected JWT audience (aud claim)")

    # Telemetry Settings
    telemetry_enabled: bool = Field(default=True, description="Enable telemetry")
    telemetry_app_insights_connection_string: Optional[str] = Field(
        default=None, description="Application Insights connection string"
    )
    telemetry_app_id: str = Field(default="amplifier-app-api", description="Application identifier")
    telemetry_environment: str = Field(default="development", description="Telemetry environment tag")
    telemetry_sample_rate: float = Field(default=1.0, description="Telemetry sampling rate")
    telemetry_sample_rate_errors: float = Field(default=1.0, description="Error sampling rate")
    telemetry_sanitize_pii: bool = Field(default=True, description="Sanitize PII in telemetry")
    telemetry_truncate_large_payloads: bool = Field(default=True, description="Truncate large payloads")
    telemetry_max_payload_size: int = Field(default=10000, description="Max payload size in chars")
    telemetry_flush_interval_seconds: int = Field(default=5, description="Telemetry flush interval")
    telemetry_enable_dev_logger: bool = Field(default=True, description="Enable dev file logger")
    telemetry_dev_logger_max_size_mb: int = Field(default=10, description="Dev logger max file size")
    telemetry_track_request_headers: bool = Field(default=False, description="Track request headers")
    telemetry_track_response_headers: bool = Field(default=False, description="Track response headers")
    telemetry_track_request_body: bool = Field(default=False, description="Track request body")
    telemetry_track_response_body: bool = Field(default=False, description="Track response body")

    @field_validator("environment", mode="before")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment is one of allowed values."""
        allowed = {"development", "test", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v

    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    def is_development(self) -> bool:
        """Check if running in local development."""
        return self.environment == "development"

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
```

---

## Environment Configuration Files

### .env.development (Local Development)

```bash
# Environment
ENVIRONMENT=development

# Service Settings
SERVICE_HOST=0.0.0.0
SERVICE_PORT=8765
SERVICE_WORKERS=1  # Single worker for easier debugging
LOG_LEVEL=debug

# Database - Local PostgreSQL in Docker
DATABASE_URL=postgresql+asyncpg://amplifier_dev:dev_password@localhost:5432/amplifier_dev
DATABASE_POOL_MIN_SIZE=2
DATABASE_POOL_MAX_SIZE=5

# Security (weak credentials OK for local)
SECRET_KEY=development-secret-key-not-secure
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24 hours for convenience

# CORS (allow all local ports)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:8080,http://localhost:4200

# Amplifier Core Paths (local forks)
AMPLIFIER_CORE_PATH=../amplifier-core
AMPLIFIER_FOUNDATION_PATH=../amplifier-foundation

# API Keys (for LLM providers)
ANTHROPIC_API_KEY=your-dev-key-here
OPENAI_API_KEY=
AZURE_OPENAI_API_KEY=
GOOGLE_API_KEY=

# Session Storage
SESSION_STORAGE_PATH=./sessions
MAX_SESSION_AGE_DAYS=7  # Clean up quickly in dev

# Rate Limiting (very relaxed for local dev)
RATE_LIMIT_REQUESTS_PER_MINUTE=1000

# Authentication (relaxed for local dev)
AUTH_MODE=api_key_jwt
AUTH_REQUIRED=false
API_KEY_HEADER=X-API-Key

# JWT Settings (local testing)
JWT_ALGORITHM=HS256  # Symmetric for easier testing
JWT_PUBLIC_KEY_URL=
JWT_ISSUER=
JWT_AUDIENCE=

# Telemetry Settings
TELEMETRY_ENABLED=true
TELEMETRY_APP_INSIGHTS_CONNECTION_STRING=  # Empty - use dev logger
TELEMETRY_APP_ID=amplifier-app-api
TELEMETRY_ENVIRONMENT=development
TELEMETRY_SAMPLE_RATE=1.0
TELEMETRY_SAMPLE_RATE_ERRORS=1.0
TELEMETRY_SANITIZE_PII=false  # See full data in dev
TELEMETRY_TRUNCATE_LARGE_PAYLOADS=false  # See full payloads
TELEMETRY_MAX_PAYLOAD_SIZE=100000
TELEMETRY_FLUSH_INTERVAL_SECONDS=5
TELEMETRY_ENABLE_DEV_LOGGER=true
TELEMETRY_DEV_LOGGER_MAX_SIZE_MB=50
TELEMETRY_TRACK_REQUEST_HEADERS=true
TELEMETRY_TRACK_RESPONSE_HEADERS=true
TELEMETRY_TRACK_REQUEST_BODY=true
TELEMETRY_TRACK_RESPONSE_BODY=true
```

**How to use:**
```bash
# Create from template
cp .env.example .env.development

# Start local PostgreSQL
docker compose -f docker-compose.dev.yml up -d postgres

# Run API with development config
ENVIRONMENT=development uvicorn amplifier_app_api.main:app --reload
```

---

### .env.test (CI/CD & Azure Test Environment)

```bash
# Environment
ENVIRONMENT=test

# Service Settings
SERVICE_HOST=0.0.0.0
SERVICE_PORT=8765
SERVICE_WORKERS=2
LOG_LEVEL=info

# Database - Azure PostgreSQL Test Instance
DATABASE_URL=postgresql+asyncpg://amplifier_admin:${POSTGRES_PASSWORD}@amplifier-db-test.postgres.database.azure.com:5432/amplifier_test?sslmode=require
DATABASE_POOL_MIN_SIZE=5
DATABASE_POOL_MAX_SIZE=10

# Security (loaded from GitHub Secrets or Key Vault)
SECRET_KEY=${SECRET_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS (test frontend URL)
ALLOWED_ORIGINS=https://test-api.azurewebsites.net

# Session Storage (Azure File Share or Blob Storage)
SESSION_STORAGE_PATH=/mnt/sessions
MAX_SESSION_AGE_DAYS=14

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=100

# Authentication
AUTH_MODE=api_key_jwt
AUTH_REQUIRED=true
API_KEY_HEADER=X-API-Key

# JWT Settings
JWT_ALGORITHM=RS256
JWT_PUBLIC_KEY_URL=${JWT_PUBLIC_KEY_URL}
JWT_ISSUER=${JWT_ISSUER}
JWT_AUDIENCE=${JWT_AUDIENCE}

# Telemetry Settings
TELEMETRY_ENABLED=true
TELEMETRY_APP_INSIGHTS_CONNECTION_STRING=${APP_INSIGHTS_CONNECTION_STRING}
TELEMETRY_APP_ID=amplifier-app-api
TELEMETRY_ENVIRONMENT=test
TELEMETRY_SAMPLE_RATE=1.0
TELEMETRY_SAMPLE_RATE_ERRORS=1.0
TELEMETRY_SANITIZE_PII=true
TELEMETRY_TRUNCATE_LARGE_PAYLOADS=true
TELEMETRY_MAX_PAYLOAD_SIZE=10000
TELEMETRY_FLUSH_INTERVAL_SECONDS=10
TELEMETRY_ENABLE_DEV_LOGGER=false
TELEMETRY_TRACK_REQUEST_HEADERS=false
TELEMETRY_TRACK_RESPONSE_HEADERS=false
TELEMETRY_TRACK_REQUEST_BODY=false
TELEMETRY_TRACK_RESPONSE_BODY=false
```

**How to use in CI:**
```yaml
# .github/workflows/test.yml
env:
  ENVIRONMENT: test
  POSTGRES_PASSWORD: ${{ secrets.TEST_POSTGRES_PASSWORD }}
  SECRET_KEY: ${{ secrets.TEST_SECRET_KEY }}
  APP_INSIGHTS_CONNECTION_STRING: ${{ secrets.TEST_APP_INSIGHTS }}
```

---

### .env.production (Azure App Service)

```bash
# Environment
ENVIRONMENT=production

# Service Settings
SERVICE_HOST=0.0.0.0
SERVICE_PORT=8000
SERVICE_WORKERS=4
LOG_LEVEL=warning

# Database - Loaded from Azure Key Vault
# Do NOT hardcode connection string here!
AZURE_KEYVAULT_NAME=kv-amplifier-prod

# Connection will be loaded via managed identity
# Secret name in Key Vault: "postgresql-connection-string"

# Database Pool Settings
DATABASE_POOL_MIN_SIZE=10
DATABASE_POOL_MAX_SIZE=30

# Security - Loaded from Key Vault
# Secret names: "jwt-secret-key", "app-insights-connection-string"

# CORS (production frontend only)
ALLOWED_ORIGINS=https://app.yourdomain.com,https://www.yourdomain.com

# Session Storage (Azure File Share)
SESSION_STORAGE_PATH=/mnt/sessions
MAX_SESSION_AGE_DAYS=90

# Rate Limiting (strict)
RATE_LIMIT_REQUESTS_PER_MINUTE=60

# Authentication (enforced)
AUTH_MODE=api_key_jwt
AUTH_REQUIRED=true
API_KEY_HEADER=X-API-Key

# JWT Settings (loaded from Key Vault or env vars)
JWT_ALGORITHM=RS256
JWT_PUBLIC_KEY_URL=https://yourdomain.auth0.com/.well-known/jwks.json
JWT_ISSUER=https://yourdomain.auth0.com/
JWT_AUDIENCE=https://api.yourdomain.com

# Telemetry Settings
TELEMETRY_ENABLED=true
# App Insights connection string loaded from Key Vault
TELEMETRY_APP_ID=amplifier-app-api
TELEMETRY_ENVIRONMENT=production
TELEMETRY_SAMPLE_RATE=0.1  # Sample 10% in production
TELEMETRY_SAMPLE_RATE_ERRORS=1.0  # All errors
TELEMETRY_SANITIZE_PII=true
TELEMETRY_TRUNCATE_LARGE_PAYLOADS=true
TELEMETRY_MAX_PAYLOAD_SIZE=5000
TELEMETRY_FLUSH_INTERVAL_SECONDS=30
TELEMETRY_ENABLE_DEV_LOGGER=false
TELEMETRY_TRACK_REQUEST_HEADERS=false
TELEMETRY_TRACK_RESPONSE_HEADERS=false
TELEMETRY_TRACK_REQUEST_BODY=false
TELEMETRY_TRACK_RESPONSE_BODY=false
```

**How to configure in Azure App Service:**

```bash
# Set environment variable
az webapp config appsettings set \
  --name amplifier-api-prod \
  --resource-group rg-amplifier \
  --settings ENVIRONMENT=production AZURE_KEYVAULT_NAME=kv-amplifier-prod
```

---

## Azure Key Vault Integration (Production Only)

### Purpose

In production, sensitive values should **never be in environment variables**. Use Azure Key Vault with managed identity.

### Setup

1. **Create Key Vault:**
```bash
az keyvault create \
  --name kv-amplifier-prod \
  --resource-group rg-amplifier \
  --location eastus
```

2. **Store secrets:**
```bash
# PostgreSQL connection string
az keyvault secret set \
  --vault-name kv-amplifier-prod \
  --name postgresql-connection-string \
  --value "postgresql+asyncpg://amplifier_admin:STRONG_PASSWORD@amplifier-db-prod.postgres.database.azure.com:5432/amplifier_prod?sslmode=require"

# JWT secret key
az keyvault secret set \
  --vault-name kv-amplifier-prod \
  --name jwt-secret-key \
  --value "$(openssl rand -hex 32)"

# App Insights connection string
az keyvault secret set \
  --vault-name kv-amplifier-prod \
  --name app-insights-connection-string \
  --value "InstrumentationKey=xxx;..."
```

3. **Enable managed identity on App Service:**
```bash
az webapp identity assign \
  --name amplifier-api-prod \
  --resource-group rg-amplifier
```

4. **Grant App Service access to Key Vault:**
```bash
# Get the principal ID
PRINCIPAL_ID=$(az webapp identity show \
  --name amplifier-api-prod \
  --resource-group rg-amplifier \
  --query principalId -o tsv)

# Grant access
az keyvault set-policy \
  --name kv-amplifier-prod \
  --object-id $PRINCIPAL_ID \
  --secret-permissions get list
```

### Code Implementation

**Create: amplifier_app_api/utils/secrets.py**

```python
"""Azure Key Vault integration for production secrets."""

import os
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


class SecretsManager:
    """Manage secrets from Azure Key Vault in production, env vars in dev."""

    def __init__(self):
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.vault_name = os.getenv("AZURE_KEYVAULT_NAME")
        self._client: Optional[SecretClient] = None

        if self.environment == "production" and self.vault_name:
            credential = DefaultAzureCredential()
            vault_url = f"https://{self.vault_name}.vault.azure.net"
            self._client = SecretClient(vault_url=vault_url, credential=credential)

    def get_secret(self, key: str, env_var_name: Optional[str] = None) -> Optional[str]:
        """
        Get secret from Key Vault (prod) or environment variable (dev/test).

        Args:
            key: Key Vault secret name
            env_var_name: Environment variable name (defaults to key.upper().replace('-', '_'))

        Returns:
            Secret value or None if not found
        """
        # Production: Load from Key Vault
        if self._client:
            try:
                secret = self._client.get_secret(key)
                return secret.value
            except Exception as e:
                # Log but don't crash - fallback to env var
                print(f"Warning: Failed to load {key} from Key Vault: {e}")

        # Dev/Test: Load from environment variable
        env_var = env_var_name or key.upper().replace("-", "_")
        return os.getenv(env_var)


# Global instance
secrets_manager = SecretsManager()
```

**Update config.py to use Key Vault:**

```python
from amplifier_app_api.utils.secrets import secrets_manager

class Settings(BaseSettings):
    # ... existing fields ...

    @property
    def database_url_resolved(self) -> str:
        """Get database URL, loading from Key Vault in production."""
        if self.is_production():
            url = secrets_manager.get_secret("postgresql-connection-string", "DATABASE_URL")
            return url or self.database_url
        return self.database_url

    @property
    def secret_key_resolved(self) -> str:
        """Get secret key, loading from Key Vault in production."""
        if self.is_production():
            key = secrets_manager.get_secret("jwt-secret-key", "SECRET_KEY")
            return key or self.secret_key
        return self.secret_key

    @property
    def app_insights_connection_string_resolved(self) -> Optional[str]:
        """Get App Insights connection string, loading from Key Vault in production."""
        if self.is_production():
            conn_str = secrets_manager.get_secret(
                "app-insights-connection-string",
                "TELEMETRY_APP_INSIGHTS_CONNECTION_STRING"
            )
            return conn_str or self.telemetry_app_insights_connection_string
        return self.telemetry_app_insights_connection_string
```

---

## Azure Infrastructure Setup

### Recommended Resources Per Environment

| Environment | PostgreSQL Server | Tier | Database Name | Cost/Month |
|-------------|------------------|------|---------------|------------|
| **Development** | Local Docker | N/A | amplifier_dev | Free |
| **Test** | amplifier-db-test | B1ms | amplifier_test | ~$30 |
| **Production** | amplifier-db-prod | B2s | amplifier_prod | ~$60 |

### Provisioning Commands

**Test Environment:**
```bash
# Create PostgreSQL server (if not exists)
az postgres flexible-server create \
  --name amplifier-db-test \
  --resource-group rg-amplifier \
  --location eastus \
  --admin-user amplifier_admin \
  --admin-password "STRONG_PASSWORD_HERE" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32 \
  --version 15 \
  --public-access 0.0.0.0 \
  --tags environment=test managed-by=amplifier

# Create database
az postgres flexible-server db create \
  --server-name amplifier-db-test \
  --resource-group rg-amplifier \
  --database-name amplifier_test

# Allow Azure services
az postgres flexible-server firewall-rule create \
  --server-name amplifier-db-test \
  --resource-group rg-amplifier \
  --name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0

# Allow your IP for testing
az postgres flexible-server firewall-rule create \
  --server-name amplifier-db-test \
  --resource-group rg-amplifier \
  --name AllowMyIP \
  --start-ip-address YOUR_IP \
  --end-ip-address YOUR_IP
```

**Production Environment:**
```bash
# Create PostgreSQL server with high availability
az postgres flexible-server create \
  --name amplifier-db-prod \
  --resource-group rg-amplifier \
  --location eastus \
  --admin-user amplifier_admin \
  --admin-password "VERY_STRONG_PASSWORD" \
  --sku-name Standard_B2s \
  --tier Burstable \
  --storage-size 64 \
  --version 15 \
  --high-availability ZoneRedundant \
  --backup-retention 14 \
  --public-access None \
  --tags environment=production managed-by=amplifier cost-center=engineering

# Create database
az postgres flexible-server db create \
  --server-name amplifier-db-prod \
  --resource-group rg-amplifier \
  --database-name amplifier_prod

# Production uses Private Endpoint, NOT public access
# Configure VNet integration with App Service
```

---

## Local Development Workflow

### 1. Start Local PostgreSQL

```bash
# Start PostgreSQL container
docker compose -f docker-compose.dev.yml up -d postgres

# Wait for healthy
docker compose -f docker-compose.dev.yml ps

# Verify connection
docker exec amplifier-postgres-dev psql -U amplifier_dev -d amplifier_dev -c '\dt'
```

### 2. Initialize Schema

```bash
# Run migrations (or let app auto-create on first start)
ENVIRONMENT=development python -m amplifier_app_api.storage.database
```

### 3. Run API Locally

```bash
# Set environment
export ENVIRONMENT=development

# Run with auto-reload
uvicorn amplifier_app_api.main:app --reload --host 0.0.0.0 --port 8765
```

### 4. Reset Database (When Needed)

```bash
# Drop and recreate database
docker exec amplifier-postgres-dev psql -U amplifier_dev -c "DROP DATABASE IF EXISTS amplifier_dev;"
docker exec amplifier-postgres-dev psql -U amplifier_dev -c "CREATE DATABASE amplifier_dev;"

# Restart API to reinitialize schema
```

---

## Test Environment Workflow

### 1. Connect to Azure PostgreSQL Test

```bash
# Set environment
export ENVIRONMENT=test
export POSTGRES_PASSWORD="test-db-password"

# Test connection
psql "postgresql://amplifier_admin:${POSTGRES_PASSWORD}@amplifier-db-test.postgres.database.azure.com:5432/amplifier_test?sslmode=require"
```

### 2. Run Integration Tests Against Test DB

```bash
# GitHub Actions workflow
export DATABASE_URL="postgresql+asyncpg://amplifier_admin:${POSTGRES_PASSWORD}@amplifier-db-test.postgres.database.azure.com:5432/amplifier_test?sslmode=require"

pytest tests/ --maxfail=1 --disable-warnings
```

### 3. Deploy to Test App Service

```bash
# Deploy via GitHub Actions or manually
az webapp up \
  --name amplifier-api-test \
  --resource-group rg-amplifier \
  --runtime "PYTHON:3.12"
```

---

## Production Environment Workflow

### 1. Deploy via CI/CD

```yaml
# .github/workflows/deploy-prod.yml
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to Azure App Service
        uses: azure/webapps-deploy@v2
        with:
          app-name: amplifier-api-prod
          publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
```

### 2. App Service Configuration

```bash
# Set environment variable
az webapp config appsettings set \
  --name amplifier-api-prod \
  --resource-group rg-amplifier \
  --settings \
    ENVIRONMENT=production \
    AZURE_KEYVAULT_NAME=kv-amplifier-prod \
    AUTH_REQUIRED=true

# Enable managed identity (if not already done)
az webapp identity assign \
  --name amplifier-api-prod \
  --resource-group rg-amplifier
```

### 3. Database Access

Production database should **NOT** be publicly accessible:

```bash
# Use Private Endpoint with VNet integration
az postgres flexible-server update \
  --name amplifier-db-prod \
  --resource-group rg-amplifier \
  --public-access Disabled

# Connect App Service via VNet integration
# (requires additional VNet setup)
```

---

## Database URL Format by Environment

| Environment | Format |
|-------------|--------|
| **Development** | `postgresql+asyncpg://user:pass@localhost:5432/amplifier_dev` |
| **Test** | `postgresql+asyncpg://user:pass@amplifier-db-test.postgres.database.azure.com:5432/amplifier_test?sslmode=require` |
| **Production** | Loaded from Key Vault (not in env file) |

**Key differences:**
- Development: No SSL required (local container)
- Test: `sslmode=require` for Azure
- Production: `sslmode=require` + loaded from Key Vault

---

## Schema Management Across Environments

### Option 1: Auto-create Schema on Startup (Recommended)

**Current approach** - Application creates tables if they don't exist on first connection.

**Pros:**
- Simple
- Works for all environments
- No migration tool needed

**Cons:**
- Schema drift risk between environments
- No version control for schema changes

### Option 2: Migration Tool (Alembic)

**For future** when schema changes become frequent.

```bash
# Install
uv add alembic

# Initialize
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Add session_participants table"

# Apply to dev
ENVIRONMENT=development alembic upgrade head

# Apply to test
ENVIRONMENT=test alembic upgrade head

# Apply to prod
ENVIRONMENT=production alembic upgrade head
```

**Recommendation:** Stick with auto-create for now, add Alembic when you need schema versioning.

---

## Testing Strategy

### Unit Tests

```python
# tests/conftest.py
import pytest
import asyncpg
from typing import AsyncGenerator

@pytest.fixture
async def test_db_pool() -> AsyncGenerator[asyncpg.Pool, None]:
    """Create test database pool."""
    # Use separate test database
    pool = await asyncpg.create_pool(
        "postgresql+asyncpg://amplifier_dev:dev_password@localhost:5432/amplifier_test",
        min_size=2,
        max_size=5
    )
    
    # Clean database before tests
    async with pool.acquire() as conn:
        await conn.execute('DROP SCHEMA public CASCADE')
        await conn.execute('CREATE SCHEMA public')
    
    yield pool
    
    await pool.close()
```

### Integration Tests

```python
# Use environment variable to switch database
@pytest.mark.integration
async def test_session_creation():
    # Reads from DATABASE_URL env var
    # Set to test database for integration tests
    pass
```

### CI Configuration

```yaml
# .github/workflows/test.yml
jobs:
  test:
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: amplifier_dev
          POSTGRES_PASSWORD: dev_password
          POSTGRES_DB: amplifier_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://amplifier_dev:dev_password@localhost:5432/amplifier_test
        run: pytest tests/
```

---

## Environment Comparison Table

| Aspect | Development | Test | Production |
|--------|-------------|------|------------|
| **Database Location** | Local Docker | Azure PostgreSQL | Azure PostgreSQL |
| **Tier** | postgres:15-alpine | B1ms (1 vCore, 2 GB) | B2s (2 vCores, 4 GB) |
| **High Availability** | No | No | Zone-redundant |
| **Backup Retention** | No backups | 7 days | 14 days |
| **SSL** | No | Required | Required |
| **Public Access** | localhost only | Azure services + CI | Private Endpoint only |
| **Connection String** | .env.development | .env.test + GitHub Secrets | Azure Key Vault |
| **Auth Required** | No | Yes | Yes |
| **Rate Limiting** | 1000 req/min | 100 req/min | 60 req/min |
| **Telemetry Sample** | 100% | 100% | 10% |
| **Data Retention** | 7 days | 14 days | 90 days |
| **Cost** | Free | ~$30/month | ~$60/month |

---

## Security Best Practices

### Development
- ✅ Weak passwords OK
- ✅ No SSL required
- ✅ API keys in .env files
- ✅ Full telemetry (see all data)

### Test
- ✅ Moderate security
- ✅ SSL required
- ✅ Secrets in GitHub Secrets
- ✅ Firewall rules for CI

### Production
- 🔒 Strong passwords (20+ chars)
- 🔒 SSL mandatory
- 🔒 Secrets in Azure Key Vault only
- 🔒 Managed identity (no passwords in code)
- 🔒 Private Endpoint (no public access)
- 🔒 Network Security Groups
- 🔒 PII sanitization enforced
- 🔒 Minimal telemetry sampling

---

## Deployment Checklist

### First-Time Setup

**Development:**
- [ ] Create `.env.development` from template
- [ ] Start PostgreSQL container
- [ ] Run API and verify schema creation
- [ ] Create test application and API key

**Test:**
- [ ] Provision Azure PostgreSQL test server (B1ms)
- [ ] Create `amplifier_test` database
- [ ] Configure firewall for CI/CD IPs
- [ ] Store secrets in GitHub Secrets
- [ ] Deploy test App Service
- [ ] Run smoke tests

**Production:**
- [ ] Provision Azure PostgreSQL prod server (B2s, high availability)
- [ ] Create `amplifier_prod` database
- [ ] Configure Private Endpoint (no public access)
- [ ] Create Azure Key Vault
- [ ] Store all secrets in Key Vault
- [ ] Enable managed identity on App Service
- [ ] Grant Key Vault access to App Service
- [ ] Configure VNet integration
- [ ] Deploy production App Service
- [ ] Run production smoke tests
- [ ] Enable monitoring and alerts

---

## Cost Breakdown

| Environment | PostgreSQL | Key Vault | App Service | Total/Month |
|-------------|-----------|-----------|-------------|-------------|
| Development | Free (local) | N/A | N/A | $0 |
| Test | $30 (B1ms) | $0.03 | $14 (B1) | ~$44 |
| Production | $60 (B2s HA) | $0.03 | $56 (P1v2) | ~$116 |

**Total Azure Cost:** ~$160/month for test + production

---

## Troubleshooting

### "Can't connect to PostgreSQL in development"

```bash
# Check container is running
docker compose -f docker-compose.dev.yml ps

# Check logs
docker compose -f docker-compose.dev.yml logs postgres

# Restart container
docker compose -f docker-compose.dev.yml restart postgres
```

### "Key Vault access denied in production"

```bash
# Verify managed identity is enabled
az webapp identity show --name amplifier-api-prod --resource-group rg-amplifier

# Verify Key Vault policy
az keyvault show --name kv-amplifier-prod --query properties.accessPolicies
```

### "SSL connection error to Azure PostgreSQL"

```bash
# Ensure sslmode=require in connection string
DATABASE_URL=postgresql+asyncpg://...?sslmode=require

# Download SSL certificate if needed
wget https://dl.cacerts.digicert.com/DigiCertGlobalRootCA.crt.pem
```

---

## Summary

**Environment Strategy:**
- **Development:** Local PostgreSQL in Docker, no secrets management
- **Test:** Azure PostgreSQL B1ms, secrets in GitHub Secrets
- **Production:** Azure PostgreSQL B2s with HA, secrets in Key Vault with managed identity

**Connection Strategy:**
- Environment variable `ENVIRONMENT` controls which `.env.{environment}` file loads
- Production loads secrets from Key Vault via managed identity
- Dev/Test use environment variables directly

**Next Step:** Implement the code changes to support this environment strategy.
