"""Recipe data models."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Recipe(BaseModel):
    """Recipe data model - represents a complete recipe definition."""

    model_config = {"use_enum_values": True}

    recipe_id: str
    name: str
    description: str | None = None
    version: str = "1.0.0"
    recipe_data: dict[str, Any]  # Complete recipe as JSON dict
    user_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tags: dict[str, str] = Field(default_factory=dict)


class RecipeMetadata(BaseModel):
    """Recipe metadata without full recipe data."""

    recipe_id: str
    name: str
    description: str | None = None
    version: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    tags: dict[str, str] = Field(default_factory=dict)


class RecipeCreateRequest(BaseModel):
    """Request to create a new recipe."""

    name: str = Field(..., description="Recipe name", min_length=1)
    description: str | None = Field(None, description="Recipe description")
    version: str = Field("1.0.0", description="Semantic version")
    recipe_data: dict[str, Any] = Field(
        ...,
        description="Complete recipe definition as JSON",
        examples=[
            {
                "name": "example-recipe",
                "description": "Example",
                "version": "1.0.0",
                "author": "user@example.com",
                "tags": ["example"],
                "context": {"param1": "description"},
                "steps": [
                    {
                        "id": "step1",
                        "type": "bash",
                        "command": "echo 'Hello'",
                        "timeout": 30,
                    }
                ],
            }
        ],
    )
    tags: dict[str, str] = Field(default_factory=dict, description="Optional tags")

    @field_validator("recipe_data")
    @classmethod
    def validate_recipe_structure(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate recipe structure before accepting."""
        # Import here to avoid circular dependencies
        from amplifier_app_api.validators.recipe import validate_recipe_json

        validate_recipe_json(v)
        return v


class RecipeUpdateRequest(BaseModel):
    """Request to update an existing recipe."""

    name: str | None = None
    description: str | None = None
    version: str | None = None
    recipe_data: dict[str, Any] | None = None
    tags: dict[str, str] | None = None

    @field_validator("recipe_data")
    @classmethod
    def validate_recipe_structure(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate recipe structure if provided."""
        if v is not None:
            from amplifier_app_api.validators.recipe import validate_recipe_json

            validate_recipe_json(v)
        return v


class RecipeResponse(BaseModel):
    """Response with recipe data."""

    recipe_id: str
    name: str
    description: str | None = None
    version: str
    recipe_data: dict[str, Any]
    user_id: str
    created_at: datetime
    updated_at: datetime
    tags: dict[str, str] = Field(default_factory=dict)
    message: str | None = None


class RecipeListResponse(BaseModel):
    """Response with list of recipes."""

    recipes: list[RecipeMetadata]
    total: int
