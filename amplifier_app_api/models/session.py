"""Session data models."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    """Session status enumeration."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SessionMetadata(BaseModel):
    """Session metadata."""

    config_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_accessed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message_count: int = 0
    tags: dict[str, str] = Field(default_factory=dict)


class Session(BaseModel):
    """Session data model - simplified to reference a config.

    Sessions belong to users and can be accessed from any application.
    The app_id fields are for tracking/analytics only, not authorization.
    """

    model_config = {"use_enum_values": True}

    session_id: str
    config_id: str  # References a Config
    user_id: str = Field(..., description="User who owns this session (from JWT 'sub')")
    created_by_app_id: str = Field(
        ..., description="Application that created this session (for tracking)"
    )
    last_accessed_by_app_id: str | None = Field(
        default=None, description="Application that last accessed this session"
    )
    status: SessionStatus = SessionStatus.ACTIVE
    metadata: SessionMetadata
    transcript: list[dict[str, Any]] = Field(default_factory=list)
