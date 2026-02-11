"""Tests for recipe validation logic."""

import pytest

from amplifier_app_api.validators.recipe import (
    RecipeValidationError,
    validate_recipe_json,
)


class TestRecipeValidation:
    """Test recipe validation."""

    def test_valid_recipe(self):
        """Test that a valid recipe passes validation."""
        recipe = {
            "name": "test-recipe",
            "description": "Test recipe",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": ["test"],
            "context": {"param1": "description"},
            "steps": [
                {
                    "id": "step1",
                    "type": "bash",
                    "command": "echo 'test'",
                    "timeout": 30,
                }
            ],
        }
        # Should not raise
        validate_recipe_json(recipe)

    def test_missing_required_fields(self):
        """Test that missing required fields raises error."""
        recipe = {
            "name": "test-recipe",
            # Missing: description, version, author, tags, context, steps
        }
        with pytest.raises(RecipeValidationError) as exc_info:
            validate_recipe_json(recipe)
        assert "Missing required fields" in str(exc_info.value)

    def test_empty_name(self):
        """Test that empty name raises error."""
        recipe = {
            "name": "",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [{"id": "step1", "type": "bash", "command": "test", "timeout": 30}],
        }
        with pytest.raises(RecipeValidationError) as exc_info:
            validate_recipe_json(recipe)
        assert "'name' must be a non-empty string" in str(exc_info.value)

    def test_invalid_type_description(self):
        """Test that non-string description raises error."""
        recipe = {
            "name": "test",
            "description": 123,  # Should be string
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [{"id": "step1", "type": "bash", "command": "test", "timeout": 30}],
        }
        with pytest.raises(RecipeValidationError) as exc_info:
            validate_recipe_json(recipe)
        assert "'description' must be a string" in str(exc_info.value)

    def test_invalid_tags_type(self):
        """Test that non-array tags raises error."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": "should-be-array",  # Should be list
            "context": {},
            "steps": [{"id": "step1", "type": "bash", "command": "test", "timeout": 30}],
        }
        with pytest.raises(RecipeValidationError) as exc_info:
            validate_recipe_json(recipe)
        assert "'tags' must be an array" in str(exc_info.value)

    def test_invalid_context_type(self):
        """Test that non-object context raises error."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": "should-be-dict",  # Should be dict
            "steps": [{"id": "step1", "type": "bash", "command": "test", "timeout": 30}],
        }
        with pytest.raises(RecipeValidationError) as exc_info:
            validate_recipe_json(recipe)
        assert "'context' must be an object" in str(exc_info.value)

    def test_empty_steps(self):
        """Test that empty steps array raises error."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [],  # Empty array not allowed
        }
        with pytest.raises(RecipeValidationError) as exc_info:
            validate_recipe_json(recipe)
        assert "'steps' must be a non-empty array" in str(exc_info.value)


class TestStepValidation:
    """Test step-level validation."""

    def test_step_missing_required_fields(self):
        """Test that step with missing required fields raises error."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [
                {
                    "id": "step1",
                    # Missing: type, timeout
                }
            ],
        }
        with pytest.raises(RecipeValidationError) as exc_info:
            validate_recipe_json(recipe)
        assert "Step 0: missing required fields" in str(exc_info.value)

    def test_duplicate_step_ids(self):
        """Test that duplicate step IDs raise error."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [
                {"id": "step1", "type": "bash", "command": "test", "timeout": 30},
                {"id": "step1", "type": "bash", "command": "test2", "timeout": 30},  # Duplicate ID
            ],
        }
        with pytest.raises(RecipeValidationError) as exc_info:
            validate_recipe_json(recipe)
        assert "Duplicate step id: 'step1'" in str(exc_info.value)

    def test_empty_step_id(self):
        """Test that empty step ID raises error."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [{"id": "", "type": "bash", "command": "test", "timeout": 30}],
        }
        with pytest.raises(RecipeValidationError) as exc_info:
            validate_recipe_json(recipe)
        assert "'id' must be a non-empty string" in str(exc_info.value)

    def test_invalid_timeout(self):
        """Test that non-positive timeout raises error."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [{"id": "step1", "type": "bash", "command": "test", "timeout": 0}],
        }
        with pytest.raises(RecipeValidationError) as exc_info:
            validate_recipe_json(recipe)
        assert "'timeout' must be a positive number" in str(exc_info.value)

    def test_negative_timeout(self):
        """Test that negative timeout raises error."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [{"id": "step1", "type": "bash", "command": "test", "timeout": -10}],
        }
        with pytest.raises(RecipeValidationError) as exc_info:
            validate_recipe_json(recipe)
        assert "'timeout' must be a positive number" in str(exc_info.value)


class TestDependencyValidation:
    """Test step dependency validation."""

    def test_depends_on_optional(self):
        """Test that depends_on is optional."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [
                {"id": "step1", "type": "bash", "command": "test", "timeout": 30},
                # No depends_on field - should be fine
                {"id": "step2", "type": "bash", "command": "test2", "timeout": 30},
            ],
        }
        # Should not raise
        validate_recipe_json(recipe)

    def test_empty_depends_on(self):
        """Test that empty depends_on array is valid."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [
                {
                    "id": "step1",
                    "type": "bash",
                    "command": "test",
                    "timeout": 30,
                    "depends_on": [],  # Empty is valid
                }
            ],
        }
        # Should not raise
        validate_recipe_json(recipe)

    def test_valid_dependency(self):
        """Test that valid dependency passes."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [
                {"id": "step1", "type": "bash", "command": "test", "timeout": 30},
                {
                    "id": "step2",
                    "type": "bash",
                    "command": "test2",
                    "timeout": 30,
                    "depends_on": ["step1"],  # Valid - step1 defined earlier
                },
            ],
        }
        # Should not raise
        validate_recipe_json(recipe)

    def test_dependency_on_later_step(self):
        """Test that depending on a later step raises error."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [
                {
                    "id": "step1",
                    "type": "bash",
                    "command": "test",
                    "timeout": 30,
                    "depends_on": ["step2"],  # Invalid - step2 not defined yet
                },
                {"id": "step2", "type": "bash", "command": "test2", "timeout": 30},
            ],
        }
        with pytest.raises(RecipeValidationError) as exc_info:
            validate_recipe_json(recipe)
        assert "depends on 'step2' which is not defined in a previous step" in str(exc_info.value)

    def test_dependency_on_nonexistent_step(self):
        """Test that depending on nonexistent step raises error."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [
                {
                    "id": "step1",
                    "type": "bash",
                    "command": "test",
                    "timeout": 30,
                    "depends_on": ["nonexistent"],
                }
            ],
        }
        with pytest.raises(RecipeValidationError) as exc_info:
            validate_recipe_json(recipe)
        assert "depends on 'nonexistent' which is not defined" in str(exc_info.value)

    def test_depends_on_invalid_type(self):
        """Test that non-array depends_on raises error."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [
                {
                    "id": "step1",
                    "type": "bash",
                    "command": "test",
                    "timeout": 30,
                    "depends_on": "step2",  # Should be array
                }
            ],
        }
        with pytest.raises(RecipeValidationError) as exc_info:
            validate_recipe_json(recipe)
        assert "'depends_on' must be an array" in str(exc_info.value)

    def test_multiple_valid_dependencies(self):
        """Test that multiple valid dependencies pass."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [
                {"id": "step1", "type": "bash", "command": "test", "timeout": 30},
                {"id": "step2", "type": "bash", "command": "test2", "timeout": 30},
                {
                    "id": "step3",
                    "type": "bash",
                    "command": "test3",
                    "timeout": 30,
                    "depends_on": ["step1", "step2"],  # Both defined earlier
                },
            ],
        }
        # Should not raise
        validate_recipe_json(recipe)


class TestTypeSpecificValidation:
    """Test type-specific step validation."""

    def test_bash_step_requires_command(self):
        """Test that bash step requires command field."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [
                {
                    "id": "step1",
                    "type": "bash",
                    # Missing: command
                    "timeout": 30,
                }
            ],
        }
        with pytest.raises(RecipeValidationError) as exc_info:
            validate_recipe_json(recipe)
        assert "bash steps require 'command'" in str(exc_info.value)

    def test_recipe_step_requires_recipe(self):
        """Test that recipe step requires recipe field."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [
                {
                    "id": "step1",
                    "type": "recipe",
                    # Missing: recipe
                    "timeout": 30,
                }
            ],
        }
        with pytest.raises(RecipeValidationError) as exc_info:
            validate_recipe_json(recipe)
        assert "recipe steps require 'recipe'" in str(exc_info.value)

    def test_agent_step_requires_agent_and_prompt(self):
        """Test that agent step requires both agent and prompt fields."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [
                {
                    "id": "step1",
                    "type": "agent",
                    # Missing: agent, prompt
                    "timeout": 30,
                }
            ],
        }
        with pytest.raises(RecipeValidationError) as exc_info:
            validate_recipe_json(recipe)
        assert "agent steps require 'agent' and 'prompt'" in str(exc_info.value)

    def test_agent_step_missing_only_prompt(self):
        """Test that agent step with only agent raises error."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [
                {
                    "id": "step1",
                    "type": "agent",
                    "agent": "test-agent",
                    # Missing: prompt
                    "timeout": 30,
                }
            ],
        }
        with pytest.raises(RecipeValidationError) as exc_info:
            validate_recipe_json(recipe)
        assert "agent steps require 'agent' and 'prompt'" in str(exc_info.value)

    def test_valid_bash_step(self):
        """Test valid bash step."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [
                {
                    "id": "step1",
                    "type": "bash",
                    "command": "echo 'test'",
                    "timeout": 30,
                }
            ],
        }
        # Should not raise
        validate_recipe_json(recipe)

    def test_valid_recipe_step(self):
        """Test valid recipe step."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [
                {
                    "id": "step1",
                    "type": "recipe",
                    "recipe": "recipes:common/test.yaml",
                    "timeout": 30,
                }
            ],
        }
        # Should not raise
        validate_recipe_json(recipe)

    def test_valid_agent_step(self):
        """Test valid agent step."""
        recipe = {
            "name": "test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [
                {
                    "id": "step1",
                    "type": "agent",
                    "agent": "code-reviewer",
                    "prompt": "Review the changes",
                    "timeout": 30,
                }
            ],
        }
        # Should not raise
        validate_recipe_json(recipe)


class TestComplexRecipes:
    """Test validation of complex recipes."""

    def test_multi_step_recipe_with_dependencies(self):
        """Test complex recipe with multiple steps and dependencies."""
        recipe = {
            "name": "deployment-pipeline",
            "description": "Full deployment pipeline",
            "version": "1.0.0",
            "author": "devops@example.com",
            "tags": ["deployment", "ci/cd"],
            "context": {
                "environment": "target environment",
                "version": "version to deploy",
            },
            "steps": [
                {"id": "validate", "type": "bash", "command": "validate.sh", "timeout": 60},
                {
                    "id": "test",
                    "type": "recipe",
                    "recipe": "recipes:common/test-suite.yaml",
                    "timeout": 900,
                    "depends_on": ["validate"],
                },
                {
                    "id": "build",
                    "type": "bash",
                    "command": "build.sh",
                    "timeout": 600,
                    "depends_on": ["test"],
                },
                {
                    "id": "deploy",
                    "type": "bash",
                    "command": "deploy.sh",
                    "timeout": 300,
                    "depends_on": ["build"],
                },
                {
                    "id": "verify",
                    "type": "agent",
                    "agent": "health-checker",
                    "prompt": "Verify deployment",
                    "timeout": 120,
                    "depends_on": ["deploy"],
                },
            ],
        }
        # Should not raise
        validate_recipe_json(recipe)
