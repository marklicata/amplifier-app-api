"""Recipe management endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..core.recipe_manager import RecipeManager
from ..middleware.auth import get_current_user
from ..models.recipe import (
    RecipeCreateRequest,
    RecipeListResponse,
    RecipeResponse,
    RecipeUpdateRequest,
)
from ..storage import get_db
from ..validators.recipe import RecipeValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recipes", tags=["recipes"])


async def get_recipe_manager() -> RecipeManager:
    """Dependency to get recipe manager instance."""
    db = await get_db()
    return RecipeManager(db)


@router.post("/", response_model=RecipeResponse, status_code=201)
async def create_recipe(
    request: RecipeCreateRequest,
    user_id: str = Depends(get_current_user),
    manager: RecipeManager = Depends(get_recipe_manager),
) -> RecipeResponse:
    """
    Create a new recipe.

    Validates recipe structure before saving to database.
    """
    try:
        recipe = await manager.create_recipe(
            user_id=user_id,
            name=request.name,
            description=request.description,
            version=request.version,
            recipe_data=request.recipe_data,
            tags=request.tags,
        )
        return RecipeResponse(**recipe.model_dump(), message="Recipe created successfully")
    except RecipeValidationError as e:
        raise HTTPException(status_code=400, detail=f"Recipe validation failed: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to create recipe")
        raise HTTPException(status_code=500, detail=f"Failed to create recipe: {str(e)}")


@router.get("/", response_model=RecipeListResponse)
async def list_recipes(
    user_id: str = Depends(get_current_user),
    manager: RecipeManager = Depends(get_recipe_manager),
    tags: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> RecipeListResponse:
    """
    List all recipes for the current user.

    Optionally filter by tags (comma-separated key:value pairs).
    """
    tag_filters = {}
    if tags:
        for tag in tags.split(","):
            if ":" in tag:
                key, value = tag.split(":", 1)
                tag_filters[key.strip()] = value.strip()

    recipes = await manager.list_recipes(
        user_id=user_id, tag_filters=tag_filters, limit=limit, offset=offset
    )
    total = await manager.db.count_recipes(user_id)

    return RecipeListResponse(recipes=recipes, total=total)


@router.get("/{recipe_id}", response_model=RecipeResponse)
async def get_recipe(
    recipe_id: str,
    user_id: str = Depends(get_current_user),
    manager: RecipeManager = Depends(get_recipe_manager),
) -> RecipeResponse:
    """Get a specific recipe by ID."""
    recipe = await manager.get_recipe(recipe_id=recipe_id, user_id=user_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return RecipeResponse(**recipe.model_dump())


@router.put("/{recipe_id}", response_model=RecipeResponse)
async def update_recipe(
    recipe_id: str,
    request: RecipeUpdateRequest,
    user_id: str = Depends(get_current_user),
    manager: RecipeManager = Depends(get_recipe_manager),
) -> RecipeResponse:
    """Update an existing recipe."""
    try:
        recipe = await manager.update_recipe(
            recipe_id=recipe_id,
            user_id=user_id,
            **request.model_dump(exclude_unset=True),
        )
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        return RecipeResponse(**recipe.model_dump(), message="Recipe updated successfully")
    except RecipeValidationError as e:
        raise HTTPException(status_code=400, detail=f"Recipe validation failed: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to update recipe")
        raise HTTPException(status_code=500, detail=f"Failed to update recipe: {str(e)}")


@router.delete("/{recipe_id}", status_code=204)
async def delete_recipe(
    recipe_id: str,
    user_id: str = Depends(get_current_user),
    manager: RecipeManager = Depends(get_recipe_manager),
) -> None:
    """Delete a recipe."""
    success = await manager.delete_recipe(recipe_id=recipe_id, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Recipe not found")
