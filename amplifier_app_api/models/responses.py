"""Response models for API endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .session import SessionStatus


class SessionInfo(BaseModel):
    """Session information summary."""

    session_id: str
    config_id: str
    status: SessionStatus
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class SessionResponse(BaseModel):
    """Response for session operations."""

    session_id: str
    config_id: str
    status: SessionStatus
    message: str | None = None


class SessionListResponse(BaseModel):
    """Response for listing sessions."""

    sessions: list[SessionInfo]
    total: int


class MessageResponse(BaseModel):
    """Response for message operations."""

    session_id: str
    response: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderInfo(BaseModel):
    """Provider information."""

    name: str
    configured: bool
    models: list[str] = Field(default_factory=list)


class BundleInfo(BaseModel):
    """Bundle information."""

    name: str
    source: str
    active: bool = False
    description: str | None = None


class BundleListResponse(BaseModel):
    """Response for listing bundles."""

    bundles: list[BundleInfo]
    active: str | None = None


class ToolInfo(BaseModel):
    """Tool information."""

    name: str
    description: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolListResponse(BaseModel):
    """Response for listing tools."""

    tools: list[ToolInfo]


class ConfigResponse(BaseModel):
    """Response for configuration queries."""

    providers: dict[str, Any] = Field(default_factory=dict)
    bundles: dict[str, Any] = Field(default_factory=dict)
    modules: dict[str, Any] = Field(default_factory=dict)
    active_bundle: str | None = None
    active_provider: str | None = None


class RecipeExecutionResponse(BaseModel):
    """Response for recipe execution."""

    execution_id: str
    status: str
    result: Any | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    uptime: str
    database_connected: bool


class VersionResponse(BaseModel):
    """Version information response."""

    service_version: str
    amplifier_core_version: str | None = None
    amplifier_foundation_version: str | None = None
