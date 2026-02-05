"""Application data models for multi-tenant authentication."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class Application(BaseModel):
    """Application registration model.

    Represents a registered application (mobile app, web app, etc.)
    that can call the API on behalf of users.
    """

    app_id: str = Field(..., description="Unique application identifier (e.g., 'mobile-app')")
    app_name: str = Field(..., description="Human-readable application name")
    api_key_hash: str = Field(..., description="Bcrypt hash of the API key")
    is_active: bool = Field(default=True, description="Whether the application is active")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Application-specific settings (rate limits, features, etc.)",
    )


class ApplicationCreate(BaseModel):
    """Request to create a new application."""

    app_id: str = Field(
        ...,
        description="Unique application identifier",
        pattern="^[a-z0-9-]+$",
        examples=["mobile-app", "web-app", "desktop-app"],
    )
    app_name: str = Field(
        ..., description="Human-readable name", examples=["Mobile App", "Web App"]
    )
    settings: dict[str, Any] = Field(
        default_factory=dict, description="Optional application settings"
    )


class ApplicationResponse(BaseModel):
    """Response when creating an application."""

    app_id: str
    app_name: str
    api_key: str = Field(..., description="API key - save this! Won't be shown again")
    is_active: bool
    created_at: datetime
    message: str = "Application registered successfully"


class ApplicationInfo(BaseModel):
    """Application information (without sensitive data)."""

    app_id: str
    app_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
