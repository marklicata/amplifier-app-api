"""Middleware for authentication and request processing."""

from .auth import AuthMiddleware

__all__ = ["AuthMiddleware"]
