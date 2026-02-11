"""Config data models."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class Config(BaseModel):
    """Config data model - represents a complete bundle configuration."""

    model_config = {"use_enum_values": True}

    config_id: str
    name: str  # Human-readable name
    description: str | None = None
    config_data: dict[str, Any]  # The complete bundle configuration as dict
    user_id: str | None = None  # User who owns this config
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tags: dict[str, str] = Field(default_factory=dict)


class ConfigMetadata(BaseModel):
    """Config metadata without the full YAML content."""

    config_id: str
    name: str
    description: str | None = None
    user_id: str | None = None
    created_at: datetime
    updated_at: datetime
    tags: dict[str, str] = Field(default_factory=dict)


class ConfigCreateRequest(BaseModel):
    """Request to create a new config.

    A config is a complete bundle containing all components needed
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
    config_data: dict[str, Any] = Field(
        ...,
        description="Complete bundle configuration as JSON object with all sections (bundle, session, providers, tools, etc.)",
        examples=[{"bundle": {"name": "dev-config", "version": "1.0.0"}}],
    )
    session: dict[str, Any] | None = Field(
        None,
        description="Session configuration (orchestrator & context manager). Can be provided here or inside config_data.",
        examples=[
            {
                "orchestrator": {
                    "module": "loop-streaming",
                    "source": "git+https://github.com/microsoft/amplifier-module-loop-streaming@main",
                    "config": {"extended_thinking": True},
                },
                "context": {
                    "module": "context-simple",
                    "source": "git+https://github.com/microsoft/amplifier-module-context-simple@main",
                    "config": {
                        "max_tokens": 3000000,
                        "compact_threshold": 0.8,
                        "auto_compact": True,
                    },
                },
            }
        ],
    )
    providers: list[dict[str, Any]] | None = Field(
        None,
        description="List of providers. Can be provided here or inside config_data.",
        examples=[
            {
                "module": "provider-anthropic",
                "source": "git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
                "config": {"api_key": "sk-ant-XXXX", "model": "claude-sonnet-4-5"},
            }
        ],
    )
    includes: list[dict[str, str]] | None = Field(
        None,
        description="Optional list of includes to reference other bundles or configs.",
        examples=[{"bundle": "git+..."}],
    )
    tools: list[dict[str, str]] | None = Field(
        None,
        description="Optional list of tools to include in the config.",
        examples=[
            {
                "module": "tool-filesystem",
                "source": "git+https://github.com/microsoft/amplifier-module-tool-filesystem@main",
            },
            {
                "module": "tool-bash",
                "source": "git+https://github.com/microsoft/amplifier-module-tool-bash@main",
            },
            {
                "module": "tool-web",
                "source": "git+https://github.com/microsoft/amplifier-module-tool-web@main",
            },
            {
                "module": "tool-search",
                "source": "git+https://github.com/microsoft/amplifier-module-tool-search@main",
            },
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
    config_data: dict[str, Any] | None = None  # Updated config data
    session: dict[str, Any] | None = Field(
        None,
        description="Optional session configuration update (orchestrator & context manager).",
    )
    providers: list[dict[str, Any]] | None = Field(
        None,
        description="Optional providers list update.",
    )
    includes: list[dict[str, str]] | None = Field(
        None,
        description="Optional includes list update.",
    )
    tools: list[dict[str, str]] | None = Field(
        None,
        description="Optional tools list update.",
    )
    tags: dict[str, str] | None = None


class ConfigResponse(BaseModel):
    """Response with config data."""

    config_id: str
    name: str
    description: str | None = None
    config_data: dict[str, Any]
    user_id: str | None = None
    created_at: datetime
    updated_at: datetime
    tags: dict[str, str] = Field(default_factory=dict)
    message: str | None = None


class ConfigListResponse(BaseModel):
    """Response with list of configs."""

    configs: list[ConfigMetadata]
    total: int
