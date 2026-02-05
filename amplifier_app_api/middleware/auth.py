"""Authentication middleware for API key and JWT verification."""

import logging
from collections.abc import Callable

import bcrypt
import jwt
from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..config import settings

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for authenticating requests with API key + JWT.

    Validates:
    1. API key (X-API-Key header) -> extracts app_id
    2. JWT (Authorization: Bearer) -> extracts user_id

    Sets on request.state:
    - app_id: Application identifier
    - user_id: User identifier from JWT 'sub' claim
    """

    # Paths that don't require authentication
    PUBLIC_PATHS = [
        "/",
        "/health",
        "/version",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/applications",  # Need to register to get API keys!
    ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through authentication."""
        # Skip auth for public endpoints
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        # Allow all /applications paths (need to register to get API keys!)
        if request.url.path.startswith("/applications"):
            return await call_next(request)

        # Skip auth if not required (dev mode)
        if not settings.auth_required:
            request.state.app_id = "dev-app"
            request.state.user_id = "dev-user"
            logger.debug("Auth disabled - using dev credentials")
            return await call_next(request)

        try:
            # Authenticate based on mode
            if settings.auth_mode == "api_key_jwt":
                app_id = await self._verify_api_key(request)
                user_id = await self._verify_jwt(request)
            elif settings.auth_mode == "jwt_only":
                app_id, user_id = await self._verify_jwt_with_app_claim(request)
            else:
                return JSONResponse(
                    status_code=500,
                    content={"detail": f"Invalid auth mode: {settings.auth_mode}"}
                )

            # Set authenticated context
            request.state.app_id = app_id
            request.state.user_id = user_id

            logger.info(f"Authenticated request: app_id={app_id}, user_id={user_id}")
            return await call_next(request)

        except HTTPException as e:
            # Convert HTTPException to JSONResponse
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail}
            )
        except Exception as e:
            logger.error(f"Authentication error: {e}", exc_info=True)
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication failed"}
            )

    async def _verify_api_key(self, request: Request) -> str:
        """Verify API key and return app_id.

        Args:
            request: FastAPI request

        Returns:
            app_id extracted from valid API key

        Raises:
            HTTPException: If API key missing or invalid
        """
        api_key = request.headers.get(settings.api_key_header)
        if not api_key:
            raise HTTPException(status_code=401, detail=f"Missing {settings.api_key_header} header")

        # Get database connection - use global instance for tests
        from ..storage.database import get_db

        try:
            db = await get_db()
        except Exception as e:
            logger.error(f"Failed to get database: {e}")
            raise HTTPException(status_code=503, detail="Database not available")

        # Look up application by API key
        if not db._connection:
            raise HTTPException(status_code=503, detail="Database not available")

        cursor = await db._connection.execute(
            "SELECT app_id, api_key_hash, is_active FROM applications"
        )
        applications = await cursor.fetchall()

        for app in applications:
            # Verify the API key against stored hash
            if bcrypt.checkpw(api_key.encode(), app["api_key_hash"].encode()):
                if not app["is_active"]:
                    raise HTTPException(status_code=401, detail="Application is disabled")
                return app["app_id"]

        raise HTTPException(status_code=401, detail="Invalid API key")

    async def _verify_jwt(self, request: Request) -> str:
        """Verify JWT and return user_id.

        Args:
            request: FastAPI request

        Returns:
            user_id from JWT 'sub' claim

        Raises:
            HTTPException: If JWT missing, invalid, or expired
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid Authorization header (expected: Bearer <token>)",
            )

        token = auth_header.split(" ")[1]

        try:
            # For development: use HS256 with secret key
            # For production: use RS256 with public key from JWKS endpoint
            if settings.jwt_algorithm == "HS256":
                payload = jwt.decode(
                    token,
                    settings.secret_key,
                    algorithms=["HS256"],
                )
            else:
                # RS256: Fetch public key from JWKS endpoint
                # (Simplified - in production use proper JWKS fetching with caching)
                if not settings.jwt_public_key_url:
                    raise HTTPException(
                        status_code=500,
                        detail="JWT public key URL not configured for RS256",
                    )

                # For now, just decode without verification for RS256
                # Production: Implement proper JWKS public key fetching with caching
                payload = jwt.decode(
                    token,
                    options={"verify_signature": False},
                    algorithms=["RS256"],
                )

            # Extract user_id from 'sub' claim
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(status_code=401, detail="JWT missing 'sub' claim (user_id)")

            # Verify issuer if configured
            if settings.jwt_issuer and payload.get("iss") != settings.jwt_issuer:
                raise HTTPException(status_code=401, detail="Invalid JWT issuer")

            # Verify audience if configured
            if settings.jwt_audience and payload.get("aud") != settings.jwt_audience:
                raise HTTPException(status_code=401, detail="Invalid JWT audience")

            return user_id

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="JWT expired")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid JWT: {str(e)}")

    async def _verify_jwt_with_app_claim(self, request: Request) -> tuple[str, str]:
        """Verify JWT with embedded app_id claim.

        For auth_mode='jwt_only', expects JWT to contain both user_id (sub)
        and app_id as custom claims.

        Args:
            request: FastAPI request

        Returns:
            Tuple of (app_id, user_id)

        Raises:
            HTTPException: If JWT invalid or missing required claims
        """
        user_id = await self._verify_jwt(request)

        # Extract the token again to get app_id claim
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.split(" ")[1]

        if settings.jwt_algorithm == "HS256":
            payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        else:
            payload = jwt.decode(token, options={"verify_signature": False}, algorithms=["RS256"])

        app_id = payload.get("app_id")
        if not app_id:
            raise HTTPException(
                status_code=401,
                detail="JWT missing 'app_id' claim (required for jwt_only mode)",
            )

        return app_id, user_id
