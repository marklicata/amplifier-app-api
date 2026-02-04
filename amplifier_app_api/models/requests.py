"""Request models for API endpoints."""

from typing import Any

from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    """Request to create a new session from a config.

    A session is a runtime instance that references a config (complete YAML bundle).
    Multiple sessions can be created from the same config.
    """

    config_id: str = Field(
        ...,
        description="Config ID to use for this session (must exist)",
        examples=["c7a3f9e2-1b4d-4c8a-9f2e-d6b8a1c5e3f7"],
    )
    tags: dict[str, str] = Field(
        default_factory=dict,
        description="Optional metadata tags for this session",
        examples=[{"project": "my-app", "user": "john"}],
    )


class MessageRequest(BaseModel):
    """Request to send a message to a session."""

    message: str = Field(..., description="User message content")
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context")


class ProviderConfigRequest(BaseModel):
    """Request to configure a provider."""

    provider: str = Field(..., description="Provider name (anthropic, openai, etc.)")
    api_key: str | None = Field(default=None, description="API key")
    config: dict[str, Any] = Field(default_factory=dict, description="Provider-specific config")
    scope: str = Field(default="global", description="Config scope (local/project/global)")


class ConfigUpdateRequest(BaseModel):
    """Request to update configuration."""

    providers: dict[str, Any] | None = Field(default=None, description="Provider configs")
    bundles: dict[str, Any] | None = Field(default=None, description="Bundle configs")
    modules: dict[str, Any] | None = Field(default=None, description="Module configs")


class BundleAddRequest(BaseModel):
    """Request to add a bundle."""

    source: str = Field(..., description="Bundle source (git URL or path)")
    name: str | None = Field(default=None, description="Bundle alias")
    scope: str = Field(default="global", description="Bundle scope")


class RecipeExecuteRequest(BaseModel):
    """Request to execute a recipe."""

    recipe_path: str = Field(..., description="Path to recipe YAML")
    context: dict[str, Any] = Field(default_factory=dict, description="Recipe context variables")


class ToolInvokeRequest(BaseModel):
    """Request to invoke a tool."""

    tool_name: str = Field(..., description="Tool name to invoke")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
