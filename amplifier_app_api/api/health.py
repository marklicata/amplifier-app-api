"""Health check and version endpoints."""

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends

from .. import __version__
from ..models import HealthResponse, VersionResponse
from ..storage import Database, get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

# Track service start time
_start_time = time.time()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: Database = Depends(get_db)) -> HealthResponse:
    """Health check endpoint."""
    uptime = time.time() - _start_time

    # Check database connectivity
    db_connected = False
    try:
        # Simple test query
        await db.get_all_config()
        db_connected = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")

    return HealthResponse(
        status="healthy" if db_connected else "degraded",
        version=__version__,
        uptime_seconds=uptime,
        database_connected=db_connected,
    )


@router.get("/version", response_model=VersionResponse)
async def get_version() -> VersionResponse:
    """Get version information."""
    # TODO: Get actual versions from amplifier-core and amplifier-foundation
    return VersionResponse(
        service_version=__version__,
        amplifier_core_version=None,
        amplifier_foundation_version=None,
    )


@router.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint with service information."""
    return {
        "service": "Amplifier App api",
        "version": __version__,
        "description": "REST API service for Amplifier AI development platform",
        "docs": "/docs",
        "health": "/health",
    }
