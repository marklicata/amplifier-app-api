"""User data models for tracking and analytics."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class User(BaseModel):
    """User tracking model (optional - for analytics only).

    Tracks basic user information across applications.
    The user_id comes from the JWT 'sub' claim and represents
    the user in the external auth provider system.
    """

    user_id: str = Field(..., description="User identifier from JWT 'sub' claim")
    first_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_seen_app_id: str | None = Field(
        default=None, description="Last app this user accessed from"
    )
    total_sessions: int = Field(default=0, description="Total sessions created")
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Optional user metadata (email, name, etc. if included in JWT)",
    )
