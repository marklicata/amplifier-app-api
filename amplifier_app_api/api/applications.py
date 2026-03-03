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
        if await db.application_exists(request.app_id):
            raise HTTPException(
                status_code=409,
                detail=f"Application '{request.app_id}' already exists",
            )

        api_key = generate_api_key()
        api_key_hash = bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()
        now = await db.create_application(request.app_id, request.app_name, api_key_hash)

        logger.info(f"Application registered: {request.app_id}")

        return ApplicationResponse(
            app_id=request.app_id,
            app_name=request.app_name,
            api_key=api_key,
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
        rows = await db.list_applications()
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
        row = await db.get_application(app_id)
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
        deleted = await db.delete_application(app_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Application not found")

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
        row = await db.get_application(app_id)
        if not row:
            raise HTTPException(status_code=404, detail="Application not found")

        api_key = generate_api_key()
        api_key_hash = bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()
        await db.update_application_key(app_id, api_key_hash)

        logger.info(f"API key regenerated for: {app_id}")

        return ApplicationResponse(
            app_id=app_id,
            app_name=row["app_name"],
            api_key=api_key,
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            message="API key regenerated successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating API key: {e}")
        raise HTTPException(status_code=500, detail=str(e))
