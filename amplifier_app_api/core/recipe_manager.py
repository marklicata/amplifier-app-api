"""Recipe manager for Amplifier recipes."""

import json
import logging
import uuid
from typing import Any

from ..models.recipe import Recipe, RecipeMetadata
from ..storage import Database
from ..telemetry import track_event
from ..validators.recipe import validate_recipe_json

logger = logging.getLogger(__name__)


class RecipeManager:
    """Manages Amplifier recipes."""

    def __init__(self, db: Database):
        """Initialize recipe manager.

        Args:
            db: Database instance
        """
        self.db = db

    async def create_recipe(
        self,
        user_id: str,
        name: str,
        recipe_data: dict[str, Any],
        description: str | None = None,
        version: str = "1.0.0",
        tags: dict[str, str] | None = None,
    ) -> Recipe:
        """Create a new recipe.

        Args:
            user_id: User who owns this recipe
            name: Recipe name
            recipe_data: Complete recipe definition as dict
            description: Optional description
            version: Recipe version
            tags: Optional tags for categorization

        Returns:
            Recipe: The created recipe

        Raises:
            ValueError: If recipe structure is invalid
        """
        recipe_id = str(uuid.uuid4())

        # Validate that recipe_data is a dict
        if not isinstance(recipe_data, dict):
            raise ValueError("recipe_data must be a dictionary/object")

        # Validate recipe structure (this will raise RecipeValidationError if invalid)
        validate_recipe_json(recipe_data)

        # Serialize to JSON for storage
        recipe_json = json.dumps(recipe_data)

        recipe = Recipe(
            recipe_id=recipe_id,
            user_id=user_id,
            name=name,
            description=description,
            version=version,
            recipe_data=recipe_data,
            tags=tags or {},
        )

        await self.db.create_recipe(
            recipe_id=recipe_id,
            user_id=user_id,
            name=name,
            description=description,
            version=version,
            recipe_json=recipe_json,
            tags=tags or {},
        )

        # Track telemetry event
        track_event(
            "recipe.created",
            {
                "recipe_id": recipe_id,
                "user_id": user_id,
                "name": name,
                "version": version,
                "step_count": len(recipe_data.get("steps", [])),
            },
        )

        logger.info(f"Created recipe: {recipe_id} ({name}) for user {user_id}")
        return recipe

    async def get_recipe(self, recipe_id: str, user_id: str) -> Recipe | None:
        """Get recipe by ID.

        Args:
            recipe_id: Recipe identifier
            user_id: User who owns the recipe

        Returns:
            Recipe or None if not found
        """
        data = await self.db.get_recipe(recipe_id, user_id)
        if not data:
            return None

        return Recipe(
            recipe_id=data["recipe_id"],
            user_id=data["user_id"],
            name=data["name"],
            description=data.get("description"),
            version=data["version"],
            recipe_data=data["recipe_data"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            tags=data.get("tags", {}),
        )

    async def update_recipe(
        self,
        recipe_id: str,
        user_id: str,
        name: str | None = None,
        recipe_data: dict[str, Any] | None = None,
        description: str | None = None,
        version: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> Recipe | None:
        """Update an existing recipe.

        Args:
            recipe_id: Recipe identifier
            user_id: User who owns the recipe
            name: Updated name
            recipe_data: Updated recipe data
            description: Updated description
            version: Updated version
            tags: Updated tags

        Returns:
            Updated Recipe or None if not found

        Raises:
            ValueError: If recipe_data is invalid
        """
        recipe = await self.get_recipe(recipe_id, user_id)
        if not recipe:
            return None

        # Validate recipe_data if provided
        if recipe_data is not None:
            if not isinstance(recipe_data, dict):
                raise ValueError("recipe_data must be a dictionary/object")

            # Validate recipe structure
            validate_recipe_json(recipe_data)

        # Update fields
        updates: dict[str, Any] = {}
        if name is not None:
            updates["name"] = name
        if recipe_data is not None:
            updates["recipe_data"] = json.dumps(recipe_data)
        if description is not None:
            updates["description"] = description
        if version is not None:
            updates["version"] = version
        if tags is not None:
            updates["tags"] = tags

        await self.db.update_recipe(recipe_id, user_id, **updates)

        # Track telemetry event
        track_event(
            "recipe.updated",
            {
                "recipe_id": recipe_id,
                "user_id": user_id,
                "fields_updated": list(updates.keys()),
            },
        )

        logger.info(f"Updated recipe: {recipe_id}")
        return await self.get_recipe(recipe_id, user_id)

    async def delete_recipe(self, recipe_id: str, user_id: str) -> bool:
        """Delete a recipe.

        Args:
            recipe_id: Recipe identifier
            user_id: User who owns the recipe

        Returns:
            True if deleted, False if not found
        """
        success = await self.db.delete_recipe(recipe_id, user_id)

        if success:
            # Track telemetry event
            track_event(
                "recipe.deleted",
                {
                    "recipe_id": recipe_id,
                    "user_id": user_id,
                },
            )
            logger.info(f"Deleted recipe: {recipe_id}")

        return success

    async def list_recipes(
        self,
        user_id: str,
        tag_filters: dict[str, str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RecipeMetadata]:
        """List all recipes for a user.

        Args:
            user_id: User who owns the recipes
            tag_filters: Optional tag filters
            limit: Maximum number of recipes to return
            offset: Offset for pagination

        Returns:
            List of RecipeMetadata
        """
        recipes_data = await self.db.list_recipes(
            user_id=user_id, tag_filters=tag_filters, limit=limit, offset=offset
        )

        recipes = [
            RecipeMetadata(
                recipe_id=r["recipe_id"],
                user_id=r["user_id"],
                name=r["name"],
                description=r.get("description"),
                version=r["version"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                tags=r.get("tags", {}),
            )
            for r in recipes_data
        ]

        return recipes
