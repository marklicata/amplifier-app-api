"""Tests for recipe manager."""

import pytest
import pytest_asyncio

from amplifier_app_api.core.recipe_manager import RecipeManager
from amplifier_app_api.validators.recipe import RecipeValidationError


@pytest_asyncio.fixture
async def recipe_manager(test_db):
    """Create recipe manager with test database."""
    return RecipeManager(test_db)


@pytest_asyncio.fixture
async def test_user_id(test_db):
    """Create a test user and return the user_id."""
    user_id = "test-user-123"
    async with test_db._pool.acquire() as conn:
        # Create user if not exists
        await conn.execute(
            """
            INSERT INTO users (user_id, first_seen, last_seen)
            VALUES ($1, NOW(), NOW())
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
        )
    return user_id


@pytest_asyncio.fixture
async def sample_recipe_data():
    """Sample valid recipe data."""
    return {
        "name": "test-recipe",
        "description": "Test recipe for testing",
        "version": "1.0.0",
        "author": "test@example.com",
        "tags": ["test", "example"],
        "context": {"param1": "description of param1"},
        "steps": [
            {
                "id": "step1",
                "type": "bash",
                "command": "echo 'Hello'",
                "timeout": 30,
            },
            {
                "id": "step2",
                "type": "bash",
                "command": "echo 'World'",
                "timeout": 30,
                "depends_on": ["step1"],
            },
        ],
    }


@pytest.mark.asyncio
class TestRecipeManagerCreate:
    """Test recipe creation."""

    async def test_create_recipe_success(self, recipe_manager, test_user_id, sample_recipe_data):
        """Test successful recipe creation."""
        recipe = await recipe_manager.create_recipe(
            user_id=test_user_id,
            name="my-test-recipe",
            recipe_data=sample_recipe_data,
            description="A test recipe",
            version="1.0.0",
            tags={"category": "test"},
        )

        assert recipe.recipe_id is not None
        assert recipe.user_id == test_user_id
        assert recipe.name == "my-test-recipe"
        assert recipe.description == "A test recipe"
        assert recipe.version == "1.0.0"
        assert recipe.recipe_data == sample_recipe_data
        assert recipe.tags == {"category": "test"}
        assert recipe.created_at is not None
        assert recipe.updated_at is not None

    async def test_create_recipe_invalid_structure(self, recipe_manager, test_user_id):
        """Test creating recipe with invalid structure raises error."""
        invalid_recipe = {
            "name": "invalid",
            # Missing required fields
        }

        with pytest.raises(RecipeValidationError):
            await recipe_manager.create_recipe(
                user_id=test_user_id,
                name="invalid-recipe",
                recipe_data=invalid_recipe,
            )

    async def test_create_recipe_not_dict(self, recipe_manager, test_user_id):
        """Test creating recipe with non-dict recipe_data raises error."""
        with pytest.raises(ValueError) as exc_info:
            await recipe_manager.create_recipe(
                user_id=test_user_id,
                name="invalid-recipe",
                recipe_data="not-a-dict",  # type: ignore
            )
        assert "must be a dictionary" in str(exc_info.value)

    async def test_create_duplicate_name_same_user(
        self, recipe_manager, test_user_id, sample_recipe_data
    ):
        """Test creating recipe with duplicate name for same user fails."""
        # Create first recipe
        await recipe_manager.create_recipe(
            user_id=test_user_id,
            name="duplicate-name",
            recipe_data=sample_recipe_data,
        )

        # Try to create second recipe with same name
        with pytest.raises(Exception):  # Database unique constraint error
            await recipe_manager.create_recipe(
                user_id=test_user_id,
                name="duplicate-name",
                recipe_data=sample_recipe_data,
            )

    async def test_create_same_name_different_users(
        self, recipe_manager, test_db, sample_recipe_data
    ):
        """Test creating recipe with same name for different users succeeds."""
        # Create two users
        user1 = "test-user-1"
        user2 = "test-user-2"

        async with test_db._pool.acquire() as conn:
            for user_id in [user1, user2]:
                await conn.execute(
                    """
                    INSERT INTO users (user_id, first_seen, last_seen)
                    VALUES ($1, NOW(), NOW())
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    user_id,
                )

        # Create recipes with same name for different users
        recipe1 = await recipe_manager.create_recipe(
            user_id=user1,
            name="same-name",
            recipe_data=sample_recipe_data,
        )

        recipe2 = await recipe_manager.create_recipe(
            user_id=user2,
            name="same-name",
            recipe_data=sample_recipe_data,
        )

        assert recipe1.recipe_id != recipe2.recipe_id
        assert recipe1.user_id == user1
        assert recipe2.user_id == user2


@pytest.mark.asyncio
class TestRecipeManagerRead:
    """Test recipe retrieval."""

    async def test_get_recipe_exists(self, recipe_manager, test_user_id, sample_recipe_data):
        """Test getting existing recipe."""
        # Create recipe
        created = await recipe_manager.create_recipe(
            user_id=test_user_id,
            name="test-get",
            recipe_data=sample_recipe_data,
        )

        # Get recipe
        fetched = await recipe_manager.get_recipe(created.recipe_id, test_user_id)

        assert fetched is not None
        assert fetched.recipe_id == created.recipe_id
        assert fetched.name == created.name
        assert fetched.recipe_data == sample_recipe_data

    async def test_get_recipe_not_exists(self, recipe_manager, test_user_id):
        """Test getting nonexistent recipe returns None."""
        fetched = await recipe_manager.get_recipe("nonexistent-id", test_user_id)
        assert fetched is None

    async def test_get_recipe_wrong_user(self, recipe_manager, test_db, sample_recipe_data):
        """Test getting recipe with wrong user returns None."""
        # Create two users
        user1 = "test-user-1"
        user2 = "test-user-2"

        async with test_db._pool.acquire() as conn:
            for user_id in [user1, user2]:
                await conn.execute(
                    """
                    INSERT INTO users (user_id, first_seen, last_seen)
                    VALUES ($1, NOW(), NOW())
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    user_id,
                )

        # User1 creates recipe
        recipe = await recipe_manager.create_recipe(
            user_id=user1,
            name="user1-recipe",
            recipe_data=sample_recipe_data,
        )

        # User2 tries to get it
        fetched = await recipe_manager.get_recipe(recipe.recipe_id, user2)
        assert fetched is None

    async def test_list_recipes_empty(self, recipe_manager, test_user_id):
        """Test listing recipes when none exist."""
        recipes = await recipe_manager.list_recipes(test_user_id)
        assert recipes == []

    async def test_list_recipes_multiple(self, recipe_manager, test_user_id, sample_recipe_data):
        """Test listing multiple recipes."""
        # Create multiple recipes
        for i in range(3):
            await recipe_manager.create_recipe(
                user_id=test_user_id,
                name=f"recipe-{i}",
                recipe_data=sample_recipe_data,
            )

        recipes = await recipe_manager.list_recipes(test_user_id)
        assert len(recipes) == 3
        assert all(r.user_id == test_user_id for r in recipes)

    async def test_list_recipes_filtered_by_tags(
        self, recipe_manager, test_user_id, sample_recipe_data
    ):
        """Test listing recipes filtered by tags."""
        # Create recipes with different tags
        await recipe_manager.create_recipe(
            user_id=test_user_id,
            name="recipe-1",
            recipe_data=sample_recipe_data,
            tags={"category": "deployment"},
        )

        await recipe_manager.create_recipe(
            user_id=test_user_id,
            name="recipe-2",
            recipe_data=sample_recipe_data,
            tags={"category": "testing"},
        )

        await recipe_manager.create_recipe(
            user_id=test_user_id,
            name="recipe-3",
            recipe_data=sample_recipe_data,
            tags={"category": "deployment"},
        )

        # Filter by tag
        filtered = await recipe_manager.list_recipes(
            test_user_id, tag_filters={"category": "deployment"}
        )

        assert len(filtered) == 2
        assert all(r.tags.get("category") == "deployment" for r in filtered)

    async def test_list_recipes_pagination(
        self, recipe_manager, test_user_id, sample_recipe_data
    ):
        """Test recipe listing with pagination."""
        # Create 10 recipes
        for i in range(10):
            await recipe_manager.create_recipe(
                user_id=test_user_id,
                name=f"recipe-{i:02d}",
                recipe_data=sample_recipe_data,
            )

        # Get first page
        page1 = await recipe_manager.list_recipes(test_user_id, limit=5, offset=0)
        assert len(page1) == 5

        # Get second page
        page2 = await recipe_manager.list_recipes(test_user_id, limit=5, offset=5)
        assert len(page2) == 5

        # No overlap
        page1_ids = {r.recipe_id for r in page1}
        page2_ids = {r.recipe_id for r in page2}
        assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.asyncio
class TestRecipeManagerUpdate:
    """Test recipe updates."""

    async def test_update_recipe_name(self, recipe_manager, test_user_id, sample_recipe_data):
        """Test updating recipe name."""
        # Create recipe
        recipe = await recipe_manager.create_recipe(
            user_id=test_user_id,
            name="original-name",
            recipe_data=sample_recipe_data,
        )

        # Update name
        updated = await recipe_manager.update_recipe(
            recipe.recipe_id, test_user_id, name="updated-name"
        )

        assert updated is not None
        assert updated.name == "updated-name"
        assert updated.recipe_id == recipe.recipe_id

    async def test_update_recipe_data(self, recipe_manager, test_user_id, sample_recipe_data):
        """Test updating recipe data."""
        # Create recipe
        recipe = await recipe_manager.create_recipe(
            user_id=test_user_id,
            name="test-update",
            recipe_data=sample_recipe_data,
        )

        # Update recipe_data
        new_data = {**sample_recipe_data, "version": "2.0.0"}
        updated = await recipe_manager.update_recipe(
            recipe.recipe_id, test_user_id, recipe_data=new_data
        )

        assert updated is not None
        assert updated.recipe_data["version"] == "2.0.0"

    async def test_update_recipe_tags(self, recipe_manager, test_user_id, sample_recipe_data):
        """Test updating recipe tags."""
        # Create recipe
        recipe = await recipe_manager.create_recipe(
            user_id=test_user_id,
            name="test-tags",
            recipe_data=sample_recipe_data,
            tags={"old": "tag"},
        )

        # Update tags
        updated = await recipe_manager.update_recipe(
            recipe.recipe_id, test_user_id, tags={"new": "tag", "added": "value"}
        )

        assert updated is not None
        assert updated.tags == {"new": "tag", "added": "value"}

    async def test_update_recipe_not_found(self, recipe_manager, test_user_id):
        """Test updating nonexistent recipe returns None."""
        updated = await recipe_manager.update_recipe(
            "nonexistent-id", test_user_id, name="new-name"
        )
        assert updated is None

    async def test_update_recipe_invalid_data(
        self, recipe_manager, test_user_id, sample_recipe_data
    ):
        """Test updating with invalid recipe_data raises error."""
        # Create recipe
        recipe = await recipe_manager.create_recipe(
            user_id=test_user_id,
            name="test-invalid-update",
            recipe_data=sample_recipe_data,
        )

        # Try to update with invalid data
        invalid_data = {"name": "invalid"}  # Missing required fields

        with pytest.raises(RecipeValidationError):
            await recipe_manager.update_recipe(
                recipe.recipe_id, test_user_id, recipe_data=invalid_data
            )

    async def test_update_recipe_wrong_user(self, recipe_manager, test_db, sample_recipe_data):
        """Test updating recipe as wrong user returns None."""
        # Create two users
        user1 = "test-user-1"
        user2 = "test-user-2"

        async with test_db._pool.acquire() as conn:
            for user_id in [user1, user2]:
                await conn.execute(
                    """
                    INSERT INTO users (user_id, first_seen, last_seen)
                    VALUES ($1, NOW(), NOW())
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    user_id,
                )

        # User1 creates recipe
        recipe = await recipe_manager.create_recipe(
            user_id=user1,
            name="user1-recipe",
            recipe_data=sample_recipe_data,
        )

        # User2 tries to update it
        updated = await recipe_manager.update_recipe(recipe.recipe_id, user2, name="hacked")
        assert updated is None


@pytest.mark.asyncio
class TestRecipeManagerDelete:
    """Test recipe deletion."""

    async def test_delete_recipe_success(self, recipe_manager, test_user_id, sample_recipe_data):
        """Test successful recipe deletion."""
        # Create recipe
        recipe = await recipe_manager.create_recipe(
            user_id=test_user_id,
            name="to-delete",
            recipe_data=sample_recipe_data,
        )

        # Delete it
        success = await recipe_manager.delete_recipe(recipe.recipe_id, test_user_id)
        assert success is True

        # Verify it's gone
        fetched = await recipe_manager.get_recipe(recipe.recipe_id, test_user_id)
        assert fetched is None

    async def test_delete_recipe_not_found(self, recipe_manager, test_user_id):
        """Test deleting nonexistent recipe returns False."""
        success = await recipe_manager.delete_recipe("nonexistent-id", test_user_id)
        assert success is False

    async def test_delete_recipe_wrong_user(self, recipe_manager, test_db, sample_recipe_data):
        """Test deleting recipe as wrong user returns False."""
        # Create two users
        user1 = "test-user-1"
        user2 = "test-user-2"

        async with test_db._pool.acquire() as conn:
            for user_id in [user1, user2]:
                await conn.execute(
                    """
                    INSERT INTO users (user_id, first_seen, last_seen)
                    VALUES ($1, NOW(), NOW())
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    user_id,
                )

        # User1 creates recipe
        recipe = await recipe_manager.create_recipe(
            user_id=user1,
            name="user1-recipe",
            recipe_data=sample_recipe_data,
        )

        # User2 tries to delete it
        success = await recipe_manager.delete_recipe(recipe.recipe_id, user2)
        assert success is False

        # Verify it still exists for user1
        fetched = await recipe_manager.get_recipe(recipe.recipe_id, user1)
        assert fetched is not None
