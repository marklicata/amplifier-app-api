"""API endpoints for the Amplifier service."""

from .applications import router as applications_router
from .config import router as config_router
from .health import router as health_router
from .recipes import router as recipes_router
from .sessions import router as sessions_router

__all__ = [
    "applications_router",
    "sessions_router",
    "config_router",
    "recipes_router",
    "health_router",
]
