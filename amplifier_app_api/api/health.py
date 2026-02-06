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
        config_cnt = await db.count_configs()
        if config_cnt >= 0:
            db_connected = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")

    seconds_total = uptime
    # Calculate components
    days = seconds_total // 86400  # Number of full days
    seconds_remaining = seconds_total % 86400  # Remaining seconds after removing full days
    hours = seconds_remaining // 3600  # Number of full hours
    seconds_remaining = seconds_remaining % 3600  # Remaining seconds after removing full hours
    minutes = seconds_remaining // 60  # Number of full minutes
    seconds = seconds_remaining % 60  # Remaining seconds

    return HealthResponse(
        status="healthy" if db_connected else "degraded",
        version=__version__,
        uptime=f"Days: {int(days)}, Hours: {int(hours)}, Minutes: {int(minutes)}, Seconds: {int(seconds)}",
        database_connected=db_connected,
    )


@router.get("/version", response_model=VersionResponse)
async def get_version() -> VersionResponse:
    """Get version information."""
    # TODO: Get actual versions from amplifier-core and amplifier-foundation
    return VersionResponse(
        service_version=__version__,
        amplifier_core_version="976fb87335ffe398cf0c1bd1bcd3c2f2c154fc3c",
        amplifier_foundation_version="412fcb51980523c77339c32ef1ba3bc80c13b680",
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
