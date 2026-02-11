"""Tests for recipe API endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient

from amplifier_app_api.storage import get_db


@pytest_asyncio.fixture
async def test_user_id(test_db):
    """Create a test user and return the user_id."""
    user_id = "test-recipe-user"
    async with test_db._pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, first_seen, last_seen)
            VALUES ($1, NOW(), NOW())
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
        )
    yield user_id

    # Cleanup
    async with test_db._pool.acquire() as conn:
        await conn.execute("DELETE FROM recipes WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM users WHERE user_id = $1", user_id)


@pytest_asyncio.fixture
async def recipe_client(test_db, test_user_id):
    """Create test client with recipe endpoints."""
    from fastapi import FastAPI

    import amplifier_app_api.storage.database as db_module
    from amplifier_app_api.api.recipes import router as recipes_router
    from amplifier_app_api.middleware.auth import get_current_user

    test_app = FastAPI()
    test_app.include_router(recipes_router)

    # Mock auth to return test user
    test_app.dependency_overrides[get_current_user] = lambda: test_user_id
    test_app.dependency_overrides[get_db] = lambda: test_db

    original_db = db_module._db
    db_module._db = test_db

    from httpx import ASGITransport

    try:
        async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
            timeout=5.0,
        ) as client:
            yield client
    finally:
        test_app.dependency_overrides.clear()
        db_module._db = original_db


@pytest.fixture
def sample_recipe():
    """Sample valid recipe for testing."""
    return {
        "name": "test-recipe",
        "description": "Test recipe",
        "version": "1.0.0",
        "recipe_data": {
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
        },
        "tags": {"category": "test"},
    }


@pytest.mark.asyncio
class TestRecipeAPICreate:
    """Test recipe creation endpoint."""

    async def test_create_recipe_success(self, recipe_client, sample_recipe):
        """Test successful recipe creation."""
        response = await recipe_client.post("/api/recipes", json=sample_recipe)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-recipe"
        assert data["description"] == "Test recipe"
        assert data["version"] == "1.0.0"
        assert data["recipe_data"] == sample_recipe["recipe_data"]
        assert data["tags"] == {"category": "test"}
        assert "recipe_id" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert data["message"] == "Recipe created successfully"

    async def test_create_recipe_invalid_structure(self, recipe_client):
        """Test creating recipe with invalid structure."""
        invalid_recipe = {
            "name": "invalid",
            "recipe_data": {
                "name": "invalid",
                # Missing required fields
            },
        }

        response = await recipe_client.post("/api/recipes", json=invalid_recipe)
        assert response.status_code == 400
        assert "Recipe validation failed" in response.json()["detail"]

    async def test_create_recipe_missing_name(self, recipe_client, sample_recipe):
        """Test creating recipe without name."""
        del sample_recipe["name"]
        response = await recipe_client.post("/api/recipes", json=sample_recipe)
        assert response.status_code == 422  # Pydantic validation error

    async def test_create_recipe_empty_name(self, recipe_client, sample_recipe):
        """Test creating recipe with empty name."""
        sample_recipe["name"] = ""
        response = await recipe_client.post("/api/recipes", json=sample_recipe)
        assert response.status_code == 422

    async def test_create_recipe_invalid_depends_on(self, recipe_client):
        """Test creating recipe with invalid dependency."""
        recipe = {
            "name": "invalid-deps",
            "description": "Test",
            "version": "1.0.0",
            "recipe_data": {
                "name": "invalid-deps",
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
                        "depends_on": ["nonexistent"],  # Invalid
                    }
                ],
            },
        }

        response = await recipe_client.post("/api/recipes", json=recipe)
        assert response.status_code == 400
        assert "depends on 'nonexistent'" in response.json()["detail"]


@pytest.mark.asyncio
class TestRecipeAPIList:
    """Test recipe listing endpoint."""

    async def test_list_recipes_empty(self, recipe_client):
        """Test listing recipes when none exist."""
        response = await recipe_client.get("/api/recipes")

        assert response.status_code == 200
        data = response.json()
        assert data["recipes"] == []
        assert data["total"] == 0

    async def test_list_recipes_multiple(self, recipe_client, sample_recipe):
        """Test listing multiple recipes."""
        # Create 3 recipes
        for i in range(3):
            recipe = sample_recipe.copy()
            recipe["name"] = f"recipe-{i}"
            await recipe_client.post("/api/recipes", json=recipe)

        response = await recipe_client.get("/api/recipes")

        assert response.status_code == 200
        data = response.json()
        assert len(data["recipes"]) == 3
        assert data["total"] == 3

    async def test_list_recipes_with_tag_filter(self, recipe_client, sample_recipe):
        """Test listing recipes filtered by tags."""
        # Create recipes with different tags
        recipe1 = sample_recipe.copy()
        recipe1["name"] = "recipe-1"
        recipe1["tags"] = {"category": "deployment"}
        await recipe_client.post("/api/recipes", json=recipe1)

        recipe2 = sample_recipe.copy()
        recipe2["name"] = "recipe-2"
        recipe2["tags"] = {"category": "testing"}
        await recipe_client.post("/api/recipes", json=recipe2)

        # Filter by tag
        response = await recipe_client.get("/api/recipes?tags=category:deployment")

        assert response.status_code == 200
        data = response.json()
        assert len(data["recipes"]) == 1
        assert data["recipes"][0]["name"] == "recipe-1"

    async def test_list_recipes_pagination(self, recipe_client, sample_recipe):
        """Test recipe listing pagination."""
        # Create 10 recipes
        for i in range(10):
            recipe = sample_recipe.copy()
            recipe["name"] = f"recipe-{i:02d}"
            await recipe_client.post("/api/recipes", json=recipe)

        # Get first page
        response1 = await recipe_client.get("/api/recipes?limit=5&offset=0")
        assert response1.status_code == 200
        data1 = response1.json()
        assert len(data1["recipes"]) == 5

        # Get second page
        response2 = await recipe_client.get("/api/recipes?limit=5&offset=5")
        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2["recipes"]) == 5

        # Verify no overlap
        ids1 = {r["recipe_id"] for r in data1["recipes"]}
        ids2 = {r["recipe_id"] for r in data2["recipes"]}
        assert ids1.isdisjoint(ids2)


@pytest.mark.asyncio
class TestRecipeAPIGet:
    """Test recipe retrieval endpoint."""

    async def test_get_recipe_success(self, recipe_client, sample_recipe):
        """Test getting existing recipe."""
        # Create recipe
        create_response = await recipe_client.post("/api/recipes", json=sample_recipe)
        recipe_id = create_response.json()["recipe_id"]

        # Get recipe
        response = await recipe_client.get(f"/api/recipes/{recipe_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["recipe_id"] == recipe_id
        assert data["name"] == "test-recipe"
        assert data["recipe_data"] == sample_recipe["recipe_data"]

    async def test_get_recipe_not_found(self, recipe_client):
        """Test getting nonexistent recipe."""
        response = await recipe_client.get("/api/recipes/nonexistent-id")

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"


@pytest.mark.asyncio
class TestRecipeAPIUpdate:
    """Test recipe update endpoint."""

    async def test_update_recipe_name(self, recipe_client, sample_recipe):
        """Test updating recipe name."""
        # Create recipe
        create_response = await recipe_client.post("/api/recipes", json=sample_recipe)
        recipe_id = create_response.json()["recipe_id"]

        # Update name
        response = await recipe_client.put(
            f"/api/recipes/{recipe_id}", json={"name": "updated-name"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "updated-name"
        assert data["message"] == "Recipe updated successfully"

    async def test_update_recipe_description(self, recipe_client, sample_recipe):
        """Test updating recipe description."""
        # Create recipe
        create_response = await recipe_client.post("/api/recipes", json=sample_recipe)
        recipe_id = create_response.json()["recipe_id"]

        # Update description
        response = await recipe_client.put(
            f"/api/recipes/{recipe_id}", json={"description": "Updated description"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"

    async def test_update_recipe_tags(self, recipe_client, sample_recipe):
        """Test updating recipe tags."""
        # Create recipe
        create_response = await recipe_client.post("/api/recipes", json=sample_recipe)
        recipe_id = create_response.json()["recipe_id"]

        # Update tags
        response = await recipe_client.put(
            f"/api/recipes/{recipe_id}", json={"tags": {"new": "tag"}}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tags"] == {"new": "tag"}

    async def test_update_recipe_version(self, recipe_client, sample_recipe):
        """Test updating recipe version."""
        # Create recipe
        create_response = await recipe_client.post("/api/recipes", json=sample_recipe)
        recipe_id = create_response.json()["recipe_id"]

        # Update version
        response = await recipe_client.put(
            f"/api/recipes/{recipe_id}", json={"version": "2.0.0"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "2.0.0"

    async def test_update_recipe_data(self, recipe_client, sample_recipe):
        """Test updating recipe data."""
        # Create recipe
        create_response = await recipe_client.post("/api/recipes", json=sample_recipe)
        recipe_id = create_response.json()["recipe_id"]

        # Update recipe_data
        new_data = sample_recipe["recipe_data"].copy()
        new_data["version"] = "2.0.0"
        response = await recipe_client.put(f"/api/recipes/{recipe_id}", json={"recipe_data": new_data})

        assert response.status_code == 200
        data = response.json()
        assert data["recipe_data"]["version"] == "2.0.0"

    async def test_update_recipe_not_found(self, recipe_client):
        """Test updating nonexistent recipe."""
        response = await recipe_client.put(
            "/api/recipes/nonexistent-id", json={"name": "new-name"}
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"

    async def test_update_recipe_invalid_data(self, recipe_client, sample_recipe):
        """Test updating with invalid recipe data."""
        # Create recipe
        create_response = await recipe_client.post("/api/recipes", json=sample_recipe)
        recipe_id = create_response.json()["recipe_id"]

        # Try to update with invalid data
        invalid_data = {"name": "invalid"}  # Missing required fields
        response = await recipe_client.put(
            f"/api/recipes/{recipe_id}", json={"recipe_data": invalid_data}
        )

        assert response.status_code == 400
        assert "Recipe validation failed" in response.json()["detail"]


@pytest.mark.asyncio
class TestRecipeAPIDelete:
    """Test recipe deletion endpoint."""

    async def test_delete_recipe_success(self, recipe_client, sample_recipe):
        """Test successful recipe deletion."""
        # Create recipe
        create_response = await recipe_client.post("/api/recipes", json=sample_recipe)
        recipe_id = create_response.json()["recipe_id"]

        # Delete recipe
        response = await recipe_client.delete(f"/api/recipes/{recipe_id}")

        assert response.status_code == 204

        # Verify it's gone
        get_response = await recipe_client.get(f"/api/recipes/{recipe_id}")
        assert get_response.status_code == 404

    async def test_delete_recipe_not_found(self, recipe_client):
        """Test deleting nonexistent recipe."""
        response = await recipe_client.delete("/api/recipes/nonexistent-id")

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"


@pytest.mark.asyncio
class TestRecipeAPIEdgeCases:
    """Test edge cases and error handling."""

    async def test_create_recipe_very_long_name(self, recipe_client, sample_recipe):
        """Test creating recipe with very long name."""
        sample_recipe["name"] = "x" * 300  # Longer than VARCHAR(255)
        response = await recipe_client.post("/api/recipes", json=sample_recipe)

        # Should fail (database constraint or validation)
        assert response.status_code in [400, 422, 500]

    async def test_create_recipe_special_characters_in_name(self, recipe_client, sample_recipe):
        """Test creating recipe with special characters in name."""
        sample_recipe["name"] = "test-recipe-with-special-chars-!@#$%"
        response = await recipe_client.post("/api/recipes", json=sample_recipe)

        # Should succeed - special chars allowed
        assert response.status_code == 201

    async def test_list_recipes_invalid_pagination(self, recipe_client):
        """Test listing with invalid pagination parameters."""
        response = await recipe_client.get("/api/recipes?limit=-1")

        # Should handle gracefully (422 validation error)
        assert response.status_code == 422

    async def test_update_recipe_empty_payload(self, recipe_client, sample_recipe):
        """Test updating recipe with empty payload."""
        # Create recipe
        create_response = await recipe_client.post("/api/recipes", json=sample_recipe)
        recipe_id = create_response.json()["recipe_id"]

        # Update with empty payload (all fields optional)
        response = await recipe_client.put(f"/api/recipes/{recipe_id}", json={})

        # Should succeed (no changes)
        assert response.status_code == 200

    async def test_concurrent_creates_same_name(self, recipe_client, sample_recipe):
        """Test concurrent creation of recipes with same name."""
        import asyncio

        # Try to create two recipes with same name concurrently
        tasks = [
            recipe_client.post("/api/recipes", json=sample_recipe),
            recipe_client.post("/api/recipes", json=sample_recipe),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # At least one should fail due to unique constraint
        statuses = [r.status_code if not isinstance(r, Exception) else 500 for r in results]
        assert 201 in statuses  # At least one succeeds
        # The other should fail with 409 or 500 (constraint violation)
