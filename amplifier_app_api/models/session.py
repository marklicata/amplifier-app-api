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

    bundle: str | None = None
    provider: str | None = None
    model: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message_count: int = 0
    tags: dict[str, str] = Field(default_factory=dict)


class Session(BaseModel):
    """Session data model."""

    model_config = {"use_enum_values": True}

    session_id: str
    status: SessionStatus = SessionStatus.ACTIVE
    metadata: SessionMetadata = Field(default_factory=SessionMetadata)
    transcript: list[dict[str, Any]] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
