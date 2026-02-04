"""Config data models."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class Config(BaseModel):
    """Config data model - represents a complete YAML bundle configuration."""

    model_config = {"use_enum_values": True}

    config_id: str
    name: str  # Human-readable name
    description: str | None = None
    yaml_content: str  # The complete YAML bundle as string
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tags: dict[str, str] = Field(default_factory=dict)


class ConfigMetadata(BaseModel):
    """Config metadata without the full YAML content."""

    config_id: str
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    tags: dict[str, str] = Field(default_factory=dict)


class ConfigCreateRequest(BaseModel):
    """Request to create a new config."""

    name: str
    description: str | None = None
    yaml_content: str  # Complete bundle YAML
    tags: dict[str, str] = Field(default_factory=dict)


class ConfigUpdateRequest(BaseModel):
    """Request to update an existing config."""

    name: str | None = None
    description: str | None = None
    yaml_content: str | None = None  # Updated YAML
    tags: dict[str, str] | None = None


class ConfigResponse(BaseModel):
    """Response with config data."""

    config_id: str
    name: str
    description: str | None = None
    yaml_content: str
    created_at: datetime
    updated_at: datetime
    tags: dict[str, str] = Field(default_factory=dict)
    message: str | None = None


class ConfigListResponse(BaseModel):
    """Response with list of configs."""

    configs: list[ConfigMetadata]
    total: int
