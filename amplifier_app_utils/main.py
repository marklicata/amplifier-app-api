"""Main FastAPI application for Amplifier service."""

import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from .api import (
    bundles_router,
    config_router,
    health_router,
    sessions_router,
    tools_router,
)
from .config import settings
from .storage import init_database

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

    # Initialize database
    db = await init_database()
    logger.info("Database initialized")

    # TODO: Initialize amplifier-core and amplifier-foundation
    logger.info("Amplifier components initialization pending")

    logger.info("Amplifier service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Amplifier service...")
    await db.disconnect()
    logger.info("Amplifier service stopped")


# Create FastAPI application
app = FastAPI(
    title="Amplifier App Utils",
    description="REST API service for Amplifier AI development platform",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

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
app.include_router(sessions_router)
app.include_router(config_router)
app.include_router(bundles_router)
app.include_router(tools_router)

# Import and register smoke tests router (after app is defined to avoid circular import)
from .api.smoke import router as smoke_router  # noqa: E402

app.include_router(smoke_router)


def main() -> None:
    """Main entry point for running the service."""
    import uvicorn

    uvicorn.run(
        "amplifier_app_utils.main:app",
        host=settings.service_host,
        port=settings.service_port,
        workers=settings.service_workers,
        log_level=settings.log_level,
        reload=False,  # Set to True for development
    )


if __name__ == "__main__":
    main()
