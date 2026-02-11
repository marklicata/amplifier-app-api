"""Recipe validation logic."""

from typing import Any


class RecipeValidationError(ValueError):
    """Raised when recipe validation fails."""

    pass


def validate_recipe_json(recipe: dict[str, Any]) -> None:
    """
    Validate recipe JSON structure against amplifier-foundation recipe schema.

    Raises RecipeValidationError if invalid.
    """
    # Required top-level fields
    required_fields = ["name", "description", "version", "author", "tags", "context", "steps"]
    missing = [field for field in required_fields if field not in recipe]
    if missing:
        raise RecipeValidationError(f"Missing required fields: {', '.join(missing)}")

    # Validate types
    if not isinstance(recipe["name"], str) or not recipe["name"]:
        raise RecipeValidationError("'name' must be a non-empty string")

    if not isinstance(recipe["description"], str):
        raise RecipeValidationError("'description' must be a string")

    if not isinstance(recipe["version"], str):
        raise RecipeValidationError("'version' must be a string (e.g., '1.0.0')")

    if not isinstance(recipe["author"], str):
        raise RecipeValidationError("'author' must be a string")

    if not isinstance(recipe["tags"], list):
        raise RecipeValidationError("'tags' must be an array")

    if not isinstance(recipe["context"], dict):
        raise RecipeValidationError("'context' must be an object")

    if not isinstance(recipe["steps"], list) or len(recipe["steps"]) == 0:
        raise RecipeValidationError("'steps' must be a non-empty array")

    # Validate steps - track IDs in order
    step_ids_in_order = []
    for i, step in enumerate(recipe["steps"]):
        _validate_step(step, i, step_ids_in_order)
        step_ids_in_order.append(step["id"])


def _validate_step(step: dict[str, Any], index: int, previous_step_ids: list[str]) -> None:
    """
    Validate a single step.

    Args:
        step: The step to validate
        index: Position in the steps array
        previous_step_ids: List of step IDs that appear before this one
    """
    # Required fields (depends_on is optional)
    required = ["id", "type", "timeout"]
    missing = [field for field in required if field not in step]
    if missing:
        raise RecipeValidationError(
            f"Step {index}: missing required fields: {', '.join(missing)}"
        )

    # Validate id is unique
    if step["id"] in previous_step_ids:
        raise RecipeValidationError(f"Duplicate step id: '{step['id']}'")

    # Validate types
    if not isinstance(step["id"], str) or not step["id"]:
        raise RecipeValidationError(f"Step {index}: 'id' must be a non-empty string")

    if not isinstance(step["type"], str):
        raise RecipeValidationError(f"Step {index}: 'type' must be a string")

    if not isinstance(step["timeout"], (int, float)) or step["timeout"] <= 0:
        raise RecipeValidationError(f"Step {index}: 'timeout' must be a positive number")

    # Validate depends_on if present
    if "depends_on" in step:
        depends_on = step["depends_on"]
        if not isinstance(depends_on, list):
            raise RecipeValidationError(f"Step {index}: 'depends_on' must be an array")

        # Each dependency must reference a step defined earlier
        for dep in depends_on:
            if dep not in previous_step_ids:
                raise RecipeValidationError(
                    f"Step {index} ('{step['id']}'): depends on '{dep}' which is not defined "
                    f"in a previous step. Dependencies must reference earlier steps only."
                )

    # Type-specific validation
    step_type = step["type"]
    if step_type == "bash":
        if "command" not in step:
            raise RecipeValidationError(f"Step {index}: bash steps require 'command'")
    elif step_type == "recipe":
        if "recipe" not in step:
            raise RecipeValidationError(f"Step {index}: recipe steps require 'recipe'")
    elif step_type == "agent":
        if "agent" not in step or "prompt" not in step:
            raise RecipeValidationError(
                f"Step {index}: agent steps require 'agent' and 'prompt'"
            )
