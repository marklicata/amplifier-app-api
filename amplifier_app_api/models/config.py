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
    """Request to create a new config.

    A config is a complete YAML bundle containing all components needed
    to start an Amplifier session (tools, providers, orchestrator, etc.).
    """

    name: str = Field(
        ...,
        description="Human-readable name for the config",
        examples=["development", "production", "my-custom-config"],
    )
    description: str | None = Field(
        None,
        description="Optional description of what this config is for",
        examples=["Development configuration with Anthropic provider"],
    )
    yaml_content: str = Field(
        ...,
        description="Complete YAML bundle content with all sections (bundle, session, providers, tools, etc.)",
        examples=[
            """
bundle:
  name: dev-config
  version: 1.0.0

includes:
  - bundle: foundation

session:
  orchestrator: loop-streaming
  context: context-persistent

providers:
  - module: provider-anthropic
    config:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-5

tools:
  - module: tool-filesystem
  - module: tool-bash
  - module: tool-web
"""
        ],
    )
    tags: dict[str, str] = Field(
        default_factory=dict,
        description="Optional tags for categorizing/filtering configs",
        examples=[{"env": "dev", "team": "platform"}],
    )


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
