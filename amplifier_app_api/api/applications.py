"""Application management API endpoints."""

import logging
import secrets
from typing import Any

import bcrypt
from fastapi import APIRouter, Depends, HTTPException

from ..models import ApplicationCreate, ApplicationInfo, ApplicationResponse
from ..storage import Database, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/applications", tags=["applications"])


def generate_api_key() -> str:
    """Generate a secure API key.

    Format: app_{random_32_chars}
    """
    random_part = secrets.token_urlsafe(32)
    return f"app_{random_part}"


@router.post(
    "",
    response_model=ApplicationResponse,
    status_code=201,
    summary="Register a new application",
    description="""
Register a new application to access the API.

Returns an API key that must be saved - it won't be shown again!
The API key should be sent in the X-API-Key header on all requests.

Example:
```bash
curl -X POST /applications \\
  -H "Content-Type: application/json" \\
  -d '{
    "app_id": "mobile-app",
    "app_name": "Mobile App"
  }'
```

Response includes the API key - store it securely!
""",
)
async def create_application(
    request: ApplicationCreate,
    db: Database = Depends(get_db),
) -> ApplicationResponse:
    """Register a new application."""
    try:
        if not db._pool:
            raise HTTPException(status_code=503, detail="Database not connected")

        async with db._pool.acquire() as conn:
            # Check if app_id already exists
            existing = await conn.fetchval(
                "SELECT app_id FROM applications WHERE app_id = $1", request.app_id
            )
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"Application '{request.app_id}' already exists",
                )

            # Generate API key
            api_key = generate_api_key()

            # Hash the API key
            api_key_hash = bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()

            # Create application
            from datetime import UTC, datetime

            now = datetime.now(UTC)

            await conn.execute(
                """
                INSERT INTO applications
                (app_id, app_name, api_key_hash, is_active, created_at, updated_at, settings)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                """,
                request.app_id,
                request.app_name,
                api_key_hash,
                True,
                now,
                now,
                "{}",
            )

        logger.info(f"Application registered: {request.app_id}")

        return ApplicationResponse(
            app_id=request.app_id,
            app_name=request.app_name,
            api_key=api_key,  # Only time this is shown!
            is_active=True,
            created_at=now,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating application: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "",
    response_model=list[ApplicationInfo],
    summary="List all applications",
    description="Get a list of all registered applications (without API keys).",
)
async def list_applications(db: Database = Depends(get_db)) -> list[ApplicationInfo]:
    """List all registered applications."""
    try:
        if not db._pool:
            raise HTTPException(status_code=503, detail="Database not connected")

        async with db._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT app_id, app_name, is_active, created_at, updated_at
                FROM applications
                ORDER BY created_at DESC
                """
            )

        return [
            ApplicationInfo(
                app_id=row["app_id"],
                app_name=row["app_name"],
                is_active=bool(row["is_active"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing applications: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{app_id}",
    response_model=ApplicationInfo,
    summary="Get application details",
    description="Get details for a specific application (without API key).",
)
async def get_application(
    app_id: str,
    db: Database = Depends(get_db),
) -> ApplicationInfo:
    """Get application details."""
    try:
        if not db._pool:
            raise HTTPException(status_code=503, detail="Database not connected")

        async with db._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT app_id, app_name, is_active, created_at, updated_at
                FROM applications
                WHERE app_id = $1
                """,
                app_id,
            )

        if not row:
            raise HTTPException(status_code=404, detail="Application not found")

        return ApplicationInfo(
            app_id=row["app_id"],
            app_name=row["app_name"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting application: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{app_id}",
    summary="Delete application",
    description="Delete an application registration. This cannot be undone!",
)
async def delete_application(
    app_id: str,
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    """Delete an application."""
    try:
        if not db._pool:
            raise HTTPException(status_code=503, detail="Database not connected")

        async with db._pool.acquire() as conn:
            # Check if exists
            existing = await conn.fetchval(
                "SELECT app_id FROM applications WHERE app_id = $1", app_id
            )
            if not existing:
                raise HTTPException(status_code=404, detail="Application not found")

            # Delete
            await conn.execute("DELETE FROM applications WHERE app_id = $1", app_id)

        logger.info(f"Application deleted: {app_id}")
        return {"message": f"Application '{app_id}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting application: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{app_id}/regenerate-key",
    response_model=ApplicationResponse,
    summary="Regenerate API key",
    description="""
Generate a new API key for an application.

The old API key will stop working immediately!
Save the new key - it won't be shown again.
""",
)
async def regenerate_api_key(
    app_id: str,
    db: Database = Depends(get_db),
) -> ApplicationResponse:
    """Regenerate API key for an application."""
    try:
        if not db._pool:
            raise HTTPException(status_code=503, detail="Database not connected")

        async with db._pool.acquire() as conn:
            # Check if exists
            row = await conn.fetchrow(
                "SELECT app_name, is_active, created_at FROM applications WHERE app_id = $1",
                app_id,
            )

            if not row:
                raise HTTPException(status_code=404, detail="Application not found")

            # Generate new API key
            api_key = generate_api_key()
            api_key_hash = bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()

            # Update in database
            from datetime import UTC, datetime

            now = datetime.now(UTC)

            await conn.execute(
                "UPDATE applications SET api_key_hash = $1, updated_at = $2 WHERE app_id = $3",
                api_key_hash,
                now,
                app_id,
            )

        logger.info(f"API key regenerated for: {app_id}")

        return ApplicationResponse(
            app_id=app_id,
            app_name=row["app_name"],
            api_key=api_key,  # New API key
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            message="API key regenerated successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating API key: {e}")
        raise HTTPException(status_code=500, detail=str(e))
