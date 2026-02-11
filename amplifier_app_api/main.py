"""Main FastAPI application for Amplifier service."""

import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from .api import (
    applications_router,
    config_router,
    health_router,
    recipes_router,
    sessions_router,
)
from .config import settings
from .middleware.auth import AuthMiddleware
from .storage import init_database
from .telemetry import TelemetryMiddleware, flush_telemetry, initialize_telemetry

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown."""
    # Startup
    logger.info("Starting Amplifier service...")
    logger.info(f"Service version: {app.version}")
    logger.info(f"Host: {settings.service_host}:{settings.service_port}")

    # Initialize telemetry
    initialize_telemetry()
    logger.info("Telemetry initialized")

    # Initialize database
    db = await init_database()
    logger.info("Database initialized")

    # TODO: Initialize amplifier-core and amplifier-foundation
    logger.info("Amplifier components initialization pending")

    logger.info("Amplifier service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Amplifier service...")

    # Flush telemetry before shutdown
    flush_telemetry()
    logger.info("Telemetry flushed")

    await db.disconnect()
    logger.info("Amplifier service stopped")


# Create FastAPI application
app = FastAPI(
    title="Amplifier App API",
    description="""
REST API service for Amplifier AI development platform.

## Architecture

The API is built around two core primitives:

### Configs
Complete bundle configurations defining everything needed to run an Amplifier session:
- Bundle metadata (name, version, description)
- Included bundles
- Session configuration (orchestrator, context manager)
- Providers, tools, and hooks
- Agents and context mappings
- System instructions and base paths

Configs are **reusable** - create once, use for multiple sessions.

### Sessions
Lightweight runtime instances that reference a Config:
- Created from a config_id
- Maintains conversation transcript
- Tracks status and metadata

## Typical Workflow

1. **Build** a config using your app (validate with `POST /api/configs/validate`)
2. **Save** the config → Get config_id
3. **Create** session(s) from config_id → Get session_id
4. **Send** messages to session_id → Get AI responses

## Key Features

- ✅ **Config Validation**: Validate configs before saving
- ✅ **Config Reusability**: One config → unlimited sessions
- ✅ **Bundle Caching**: Prepared bundles cached for fast session creation
- ✅ **Type Safety**: Full Pydantic validation
- ✅ **Cache Invalidation**: Automatic when configs are updated

## API Endpoints

### Application Management
- `POST /api/applications` - Register application
- `GET /api/applications` - List applications
- `DELETE /api/applications/{id}` - Delete application

### Config Management
- `GET /api/configs` - List configs
- `POST /api/configs` - Create config
- `GET /api/configs/{id}` - Get config
- `PUT /api/configs/{id}` - Update config
- `DELETE /api/configs/{id}` - Delete config
- `POST /api/configs/validate` - Validate config (no save)

### Recipe Management
- `GET /api/recipes` - List recipes (user-specific)
- `POST /api/recipes` - Create recipe (validates before save)
- `GET /api/recipes/{id}` - Get recipe
- `PUT /api/recipes/{id}` - Update recipe
- `DELETE /api/recipes/{id}` - Delete recipe

### Session Management
- `GET /api/sessions` - List sessions
- `POST /api/sessions` - Create session
- `GET /api/sessions/{id}` - Get session
- `POST /api/sessions/{id}/send` - Send message
- `DELETE /api/sessions/{id}` - Delete session

### Health & Diagnostics
- `GET /api/health` - Health check
- `GET /api/smoke` - Smoke test suite
""",
    version="0.3.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Telemetry middleware (first, to capture all requests)
app.add_middleware(TelemetryMiddleware)

# Authentication middleware (before CORS, to reject unauthorized requests early)
app.add_middleware(AuthMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted host middleware (security)
if settings.service_host != "0.0.0.0":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[settings.service_host, "localhost", "127.0.0.1"],
    )

# Register routers
app.include_router(health_router)
app.include_router(applications_router)
app.include_router(sessions_router)
app.include_router(config_router)
app.include_router(recipes_router)

# Import and register smoke tests router (after app is defined to avoid circular import)
from .api.smoke import router as smoke_router  # noqa: E402

app.include_router(smoke_router)


def main() -> None:
    """Main entry point for running the service."""
    import uvicorn

    uvicorn.run(
        "amplifier_app_api.main:app",
        host=settings.service_host,
        port=settings.service_port,
        workers=settings.service_workers,
        log_level=settings.log_level,
        reload=False,  # Set to True for development
    )


if __name__ == "__main__":
    main()
