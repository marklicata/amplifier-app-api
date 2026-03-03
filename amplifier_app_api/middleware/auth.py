"""Authentication middleware for API key and JWT verification."""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

import bcrypt
import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..config import settings

logger = logging.getLogger(__name__)

# Cache GitHub username to avoid repeated subprocess calls
_github_user_cache: str | None = None

# JWKS cache: stores fetched public keys with TTL
_jwks_cache: dict[str, Any] | None = None
_jwks_cache_time: float = 0.0
_JWKS_CACHE_TTL = 3600  # 1 hour


async def _fetch_jwks(url: str) -> dict[str, Any]:
    """Fetch JWKS from the configured endpoint with caching.

    Returns cached keys if within TTL, otherwise fetches fresh keys.

    Args:
        url: JWKS endpoint URL

    Returns:
        JWKS response as dict

    Raises:
        HTTPException: If JWKS fetch fails
    """
    global _jwks_cache, _jwks_cache_time

    now = time.monotonic()
    if _jwks_cache is not None and (now - _jwks_cache_time) < _JWKS_CACHE_TTL:
        return _jwks_cache

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            jwks = response.json()

        _jwks_cache = jwks
        _jwks_cache_time = now
        logger.info(f"Fetched JWKS from {url} ({len(jwks.get('keys', []))} keys)")
        return jwks

    except Exception as e:
        logger.error(f"Failed to fetch JWKS from {url}: {e}")
        # If we have a stale cache, use it rather than failing
        if _jwks_cache is not None:
            logger.warning("Using stale JWKS cache after fetch failure")
            return _jwks_cache
        raise HTTPException(
            status_code=503,
            detail=f"Unable to fetch JWT public keys from {url}",
        )


def _get_signing_key_from_jwks(jwks: dict[str, Any], token: str) -> str:
    """Extract the correct signing key from JWKS for the given token.

    Matches the key ID (kid) from the token header against JWKS keys.

    Args:
        jwks: JWKS response dict
        token: Raw JWT token string

    Returns:
        PEM-encoded public key string

    Raises:
        HTTPException: If no matching key found
    """
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid JWT header: {e}")

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="JWT header missing 'kid' claim")

    for key_data in jwks.get("keys", []):
        if key_data.get("kid") == kid:
            public_key = RSAAlgorithm.from_jwk(key_data)
            return public_key

    raise HTTPException(
        status_code=401,
        detail=f"No matching public key found for kid '{kid}'",
    )


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for authenticating requests with API key + JWT.

    Validates:
    1. API key (X-API-Key header) -> extracts app_id
    2. JWT (Authorization: Bearer) -> extracts user_id

    Sets on request.state:
    - app_id: Application identifier
    - user_id: User identifier from JWT 'sub' claim (or GitHub username in dev mode)
    """

    # Paths that don't require authentication
    PUBLIC_PATHS = [
        "/",
        "/health",
        "/version",
        "/docs",
        "/redoc",
        "/openapi.json",
    ]

    @staticmethod
    async def _ensure_user_exists(user_id: str, app_id: str | None = None) -> None:
        """Ensure a user exists in the database.

        Args:
            user_id: User identifier
            app_id: Optional application ID
        """
        try:
            from ..storage.database import get_db

            db = await get_db()
            await db.ensure_user(user_id, app_id)
        except Exception as e:
            # Log but don't fail the request if user creation fails
            logger.warning(f"Failed to ensure user exists: {e}")

    @staticmethod
    async def _get_github_user() -> str:
        """Get GitHub username from gh CLI, with fallback to 'dev-user'.

        Uses cached value to avoid repeated subprocess calls.
        Runs gh CLI in a subprocess with timeout.

        Returns:
            GitHub username if gh CLI is authenticated, otherwise 'dev-user'
        """
        global _github_user_cache

        # Return cached value if available
        if _github_user_cache is not None:
            return _github_user_cache

        try:
            # Run gh CLI to get authenticated user
            # --jq extracts just the login field from the JSON response
            result = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "gh",
                    "api",
                    "user",
                    "--jq",
                    ".login",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=2.0,
            )

            stdout, stderr = await result.communicate()

            if result.returncode == 0 and stdout:
                username = stdout.decode().strip()
                if username:
                    _github_user_cache = username
                    logger.info(f"Using GitHub user from gh CLI: {username}")
                    return username

            # Log why gh CLI failed (helps debugging)
            if stderr:
                error_msg = stderr.decode().strip()
                logger.debug(f"gh CLI failed: {error_msg}")

        except asyncio.TimeoutError:
            logger.debug("gh CLI timed out (2s)")
        except FileNotFoundError:
            logger.debug("gh CLI not found in PATH")
        except Exception as e:
            logger.debug(f"Failed to get GitHub user: {e}")

        # Fallback to dev-user
        _github_user_cache = "dev-user"
        logger.debug("Falling back to 'dev-user'")
        return "dev-user"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through authentication."""
        # Skip auth for public endpoints
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        # Skip auth if not required (dev mode)
        if not settings.auth_required:
            request.state.app_id = "dev-app"

            # Use GitHub CLI to get user_id if enabled, otherwise use dev-user
            if settings.use_github_auth_in_dev:
                request.state.user_id = await self._get_github_user()
            else:
                request.state.user_id = "dev-user"

            # Ensure the user exists in the database
            await self._ensure_user_exists(request.state.user_id, request.state.app_id)

            logger.debug(
                f"Auth disabled - using dev credentials (app_id={request.state.app_id}, "
                f"user_id={request.state.user_id})"
            )
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
                    status_code=500, content={"detail": f"Invalid auth mode: {settings.auth_mode}"}
                )

            # Set authenticated context
            request.state.app_id = app_id
            request.state.user_id = user_id

            # Ensure the user exists in the database
            await self._ensure_user_exists(user_id, app_id)

            logger.info(f"Authenticated request: app_id={app_id}, user_id={user_id}")
            return await call_next(request)

        except HTTPException as e:
            # Convert HTTPException to JSONResponse
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
        except Exception as e:
            logger.error(f"Authentication error: {e}", exc_info=True)
            return JSONResponse(status_code=401, content={"detail": "Authentication failed"})

    async def _verify_api_key(self, request: Request) -> str:
        """Verify API key and return app_id.

        Uses key prefix for O(1) database lookup, then runs a single
        bcrypt verification in a thread to avoid blocking the event loop.

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

        # Get database connection
        from ..storage.database import get_db

        try:
            db = await get_db()
        except Exception as e:
            logger.error(f"Failed to get database: {e}")
            raise HTTPException(status_code=503, detail="Database not available")

        # Try prefix-based O(1) lookup first
        prefix = api_key[:12]
        applications = await db.find_applications_by_key_prefix(prefix)

        # Fallback to legacy keys without prefix
        if not applications:
            applications = await db.find_all_applications_for_key_check()

        for app in applications:
            # Run bcrypt in a thread to avoid blocking the event loop
            match = await asyncio.to_thread(
                bcrypt.checkpw, api_key.encode(), app["api_key_hash"].encode()
            )
            if match:
                if not app["is_active"]:
                    raise HTTPException(status_code=401, detail="Application is disabled")
                return app["app_id"]

        raise HTTPException(status_code=401, detail="Invalid API key")

    async def _verify_jwt(self, request: Request) -> str:
        """Verify JWT and return user_id.

        For HS256 (dev): verifies with the shared secret key.
        For RS256 (prod): fetches public keys from JWKS endpoint and verifies signature.

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
            if settings.jwt_algorithm == "HS256":
                payload = jwt.decode(
                    token,
                    settings.secret_key,
                    algorithms=["HS256"],
                )
            else:
                # RS256: Verify signature with public key from JWKS endpoint
                if not settings.jwt_public_key_url:
                    raise HTTPException(
                        status_code=500,
                        detail="JWT public key URL not configured for RS256",
                    )

                jwks = await _fetch_jwks(settings.jwt_public_key_url)
                public_key = _get_signing_key_from_jwks(jwks, token)

                decode_options = {}
                if settings.jwt_audience:
                    decode_options["audience"] = settings.jwt_audience

                payload = jwt.decode(
                    token,
                    public_key,
                    algorithms=["RS256"],
                    issuer=settings.jwt_issuer if settings.jwt_issuer else None,
                    options=decode_options,
                )

            # Extract user_id from 'sub' claim
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(status_code=401, detail="JWT missing 'sub' claim (user_id)")

            # Verify issuer if configured (for HS256 where it's not passed to decode)
            if settings.jwt_algorithm == "HS256":
                if settings.jwt_issuer and payload.get("iss") != settings.jwt_issuer:
                    raise HTTPException(status_code=401, detail="Invalid JWT issuer")
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
            # Token already verified in _verify_jwt; safe to decode claims without re-verifying
            # since we validated the signature above
            jwks = await _fetch_jwks(settings.jwt_public_key_url)
            public_key = _get_signing_key_from_jwks(jwks, token)
            payload = jwt.decode(token, public_key, algorithms=["RS256"])

        app_id = payload.get("app_id")
        if not app_id:
            raise HTTPException(
                status_code=401,
                detail="JWT missing 'app_id' claim (required for jwt_only mode)",
            )

        return app_id, user_id
