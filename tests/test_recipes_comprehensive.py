"""Comprehensive end-to-end tests for recipe system."""

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def recipe_client_e2e(test_db):
    """Create comprehensive test client with all dependencies."""
    from fastapi import FastAPI

    import amplifier_app_api.storage.database as db_module
    from amplifier_app_api.api.recipes import router as recipes_router
    # Auth handled by dependency injection
    from amplifier_app_api.storage import get_db

    test_app = FastAPI()
    test_app.include_router(recipes_router)

    # Create test user
    test_user_id = "e2e-test-user"

    # Cleanup any existing data first
    async with test_db._pool.acquire() as conn:
        await conn.execute("DELETE FROM recipes WHERE user_id = $1", test_user_id)
        await conn.execute("DELETE FROM users WHERE user_id = $1", test_user_id)

    async with test_db._pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, first_seen, last_seen)
            VALUES ($1, NOW(), NOW())
            """,
            test_user_id,
        )

    # Mock dependencies
    from amplifier_app_api.api.recipes import get_user_id
    test_app.dependency_overrides[get_user_id] = lambda: test_user_id
    test_app.dependency_overrides[get_db] = lambda: test_db

    original_db = db_module._db
    db_module._db = test_db

    from httpx import ASGITransport

    try:
        async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
            timeout=10.0,
        ) as client:
            yield client
    finally:
        # Cleanup
        async with test_db._pool.acquire() as conn:
            await conn.execute("DELETE FROM recipes WHERE user_id = $1", test_user_id)
            await conn.execute("DELETE FROM users WHERE user_id = $1", test_user_id)

        test_app.dependency_overrides.clear()
        db_module._db = original_db


@pytest.mark.asyncio
class TestRecipeLifecycle:
    """Test complete recipe lifecycle."""

    async def test_full_lifecycle_create_read_update_delete(self, recipe_client_e2e):
        """Test complete CRUD lifecycle of a recipe."""
        # 1. Create recipe
        create_payload = {
            "name": "deployment-pipeline",
            "description": "Deploy to production",
            "version": "1.0.0",
            "recipe_data": {
                "name": "deployment-pipeline",
                "description": "Deploy to production",
                "version": "1.0.0",
                "author": "devops@example.com",
                "tags": ["deployment", "production"],
                "context": {
                    "environment": "target environment",
                    "version": "version to deploy",
                },
                "steps": [
                    {
                        "id": "validate",
                        "type": "bash",
                        "command": "validate-env.sh",
                        "timeout": 60,
                    },
                    {
                        "id": "test",
                        "type": "bash",
                        "command": "run-tests.sh",
                        "timeout": 300,
                        "depends_on": ["validate"],
                    },
                    {
                        "id": "deploy",
                        "type": "bash",
                        "command": "deploy.sh",
                        "timeout": 600,
                        "depends_on": ["test"],
                    },
                ],
            },
            "tags": {"category": "deployment", "criticality": "high"},
        }

        create_response = await recipe_client_e2e.post("/api/recipes/", json=create_payload)
        assert create_response.status_code == 201
        recipe_id = create_response.json()["recipe_id"]
        assert recipe_id is not None

        # 2. Read recipe
        get_response = await recipe_client_e2e.get(f"/api/recipes/{recipe_id}")
        assert get_response.status_code == 200
        recipe_data = get_response.json()
        assert recipe_data["name"] == "deployment-pipeline"
        assert len(recipe_data["recipe_data"]["steps"]) == 3

        # 3. List recipes (should include our new one)
        list_response = await recipe_client_e2e.get("/api/recipes/")
        assert list_response.status_code == 200
        recipes = list_response.json()["recipes"]
        assert any(r["recipe_id"] == recipe_id for r in recipes)

        # 4. Update recipe
        update_payload = {
            "version": "1.1.0",
            "description": "Deploy to production (updated)",
            "tags": {"category": "deployment", "criticality": "high", "reviewed": "true"},
        }
        update_response = await recipe_client_e2e.put(
            f"/api/recipes/{recipe_id}", json=update_payload
        )
        assert update_response.status_code == 200
        updated_data = update_response.json()
        assert updated_data["version"] == "1.1.0"
        assert updated_data["description"] == "Deploy to production (updated)"
        assert updated_data["tags"]["reviewed"] == "true"

        # 5. Delete recipe
        delete_response = await recipe_client_e2e.delete(f"/api/recipes/{recipe_id}")
        assert delete_response.status_code == 204

        # 6. Verify deletion
        get_after_delete = await recipe_client_e2e.get(f"/api/recipes/{recipe_id}")
        assert get_after_delete.status_code == 404


@pytest.mark.asyncio
class TestComplexRecipeWorkflows:
    """Test complex real-world recipe scenarios."""

    async def test_multi_step_deployment_recipe(self, recipe_client_e2e):
        """Test creating and managing a complex multi-step deployment recipe."""
        recipe = {
            "name": "full-stack-deployment",
            "description": "Complete full-stack deployment workflow",
            "version": "2.0.0",
            "recipe_data": {
                "name": "full-stack-deployment",
                "description": "Complete full-stack deployment workflow",
                "version": "2.0.0",
                "author": "platform-team@example.com",
                "tags": ["deployment", "full-stack", "production"],
                "context": {
                    "backend_version": "Backend version to deploy",
                    "frontend_version": "Frontend version to deploy",
                    "environment": "Target environment",
                },
                "steps": [
                    {
                        "id": "pre-checks",
                        "type": "bash",
                        "command": "pre-deploy-checks.sh",
                        "timeout": 120,
                    },
                    {
                        "id": "backup-db",
                        "type": "bash",
                        "command": "backup-database.sh",
                        "timeout": 600,
                        "depends_on": ["pre-checks"],
                    },
                    {
                        "id": "deploy-backend",
                        "type": "bash",
                        "command": "deploy-backend.sh ${backend_version}",
                        "timeout": 900,
                        "depends_on": ["backup-db"],
                    },
                    {
                        "id": "run-migrations",
                        "type": "bash",
                        "command": "run-db-migrations.sh",
                        "timeout": 300,
                        "depends_on": ["deploy-backend"],
                    },
                    {
                        "id": "deploy-frontend",
                        "type": "bash",
                        "command": "deploy-frontend.sh ${frontend_version}",
                        "timeout": 600,
                        "depends_on": ["run-migrations"],
                    },
                    {
                        "id": "health-check",
                        "type": "agent",
                        "agent": "health-monitor",
                        "prompt": "Verify all services are healthy in ${environment}",
                        "timeout": 180,
                        "depends_on": ["deploy-frontend"],
                    },
                    {
                        "id": "smoke-tests",
                        "type": "bash",
                        "command": "run-smoke-tests.sh",
                        "timeout": 300,
                        "depends_on": ["health-check"],
                    },
                ],
            },
            "tags": {
                "category": "deployment",
                "type": "full-stack",
                "criticality": "high",
                "automated": "true",
            },
        }

        # Create recipe
        response = await recipe_client_e2e.post("/api/recipes/", json=recipe)
        assert response.status_code == 201
        data = response.json()

        # Verify structure
        assert len(data["recipe_data"]["steps"]) == 7
        assert data["tags"]["automated"] == "true"

        # Verify dependencies are correct
        steps = data["recipe_data"]["steps"]
        health_check_step = next(s for s in steps if s["id"] == "health-check")
        assert "deploy-frontend" in health_check_step["depends_on"]

    async def test_code_review_workflow_recipe(self, recipe_client_e2e):
        """Test creating an AI-powered code review workflow recipe."""
        recipe = {
            "name": "automated-code-review",
            "description": "AI-powered code review pipeline",
            "version": "1.0.0",
            "recipe_data": {
                "name": "automated-code-review",
                "description": "AI-powered code review pipeline",
                "version": "1.0.0",
                "author": "quality-team@example.com",
                "tags": ["review", "quality", "automation", "ai"],
                "context": {
                    "pr_number": "Pull request number to review",
                    "repo": "Repository name",
                },
                "steps": [
                    {
                        "id": "fetch-pr",
                        "type": "bash",
                        "command": "gh pr view ${pr_number} --repo ${repo} > pr-info.txt",
                        "timeout": 30,
                    },
                    {
                        "id": "get-diff",
                        "type": "bash",
                        "command": "gh pr diff ${pr_number} --repo ${repo} > changes.diff",
                        "timeout": 60,
                        "depends_on": ["fetch-pr"],
                    },
                    {
                        "id": "lint-check",
                        "type": "bash",
                        "command": "run-linters.sh",
                        "timeout": 180,
                        "depends_on": ["get-diff"],
                    },
                    {
                        "id": "security-scan",
                        "type": "bash",
                        "command": "security-scan.sh changes.diff",
                        "timeout": 300,
                        "depends_on": ["get-diff"],
                    },
                    {
                        "id": "ai-review",
                        "type": "agent",
                        "agent": "code-reviewer",
                        "prompt": "Review changes.diff for code quality, bugs, and best practices",
                        "mode": "review",
                        "timeout": 600,
                        "depends_on": ["lint-check", "security-scan"],
                    },
                    {
                        "id": "generate-report",
                        "type": "agent",
                        "agent": "report-generator",
                        "prompt": "Generate comprehensive review report",
                        "timeout": 120,
                        "depends_on": ["ai-review"],
                    },
                    {
                        "id": "post-comment",
                        "type": "bash",
                        "command": "gh pr comment ${pr_number} --repo ${repo} --body-file review-report.md",
                        "timeout": 30,
                        "depends_on": ["generate-report"],
                    },
                ],
            },
            "tags": {
                "category": "automation",
                "type": "review",
                "uses-ai": "true",
            },
        }

        response = await recipe_client_e2e.post("/api/recipes/", json=recipe)
        assert response.status_code == 201

        # Verify AI steps are correctly configured
        data = response.json()
        ai_steps = [s for s in data["recipe_data"]["steps"] if s["type"] == "agent"]
        assert len(ai_steps) == 2
        assert all("agent" in s and "prompt" in s for s in ai_steps)


@pytest.mark.asyncio
class TestRecipeFilteringAndSearch:
    """Test recipe filtering and search capabilities."""

    async def test_filter_recipes_by_multiple_tags(self, recipe_client_e2e):
        """Test filtering recipes by multiple tags."""
        # Create recipes with different tag combinations
        recipes_to_create = [
            {
                "name": "deploy-prod",
                "tags": {"category": "deployment", "environment": "production"},
            },
            {
                "name": "deploy-staging",
                "tags": {"category": "deployment", "environment": "staging"},
            },
            {
                "name": "test-suite",
                "tags": {"category": "testing", "environment": "staging"},
            },
        ]

        base_recipe_data = {
            "name": "base",
            "description": "Base",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [{"id": "step1", "type": "bash", "command": "test", "timeout": 30}],
        }

        for recipe_spec in recipes_to_create:
            payload = {
                "name": recipe_spec["name"],
                "description": "Test recipe",
                "version": "1.0.0",
                "recipe_data": {**base_recipe_data, "name": recipe_spec["name"]},
                "tags": recipe_spec["tags"],
            }
            response = await recipe_client_e2e.post("/api/recipes/", json=payload)
            assert response.status_code == 201

        # Filter by category=deployment
        response = await recipe_client_e2e.get("/api/recipes/?tags=category:deployment")
        data = response.json()
        assert len(data["recipes"]) == 2
        assert all("deployment" in r["tags"].get("category", "") for r in data["recipes"])

        # Filter by environment=staging
        response = await recipe_client_e2e.get("/api/recipes/?tags=environment:staging")
        data = response.json()
        assert len(data["recipes"]) == 2

    async def test_recipe_pagination_with_many_recipes(self, recipe_client_e2e):
        """Test pagination with many recipes."""
        # Create 25 recipes
        base_recipe_data = {
            "name": "base",
            "description": "Base",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [{"id": "step1", "type": "bash", "command": "test", "timeout": 30}],
        }

        for i in range(25):
            payload = {
                "name": f"recipe-{i:03d}",
                "description": f"Recipe number {i}",
                "version": "1.0.0",
                "recipe_data": {**base_recipe_data, "name": f"recipe-{i:03d}"},
                "tags": {"index": str(i)},
            }
            response = await recipe_client_e2e.post("/api/recipes/", json=payload)
            assert response.status_code == 201

        # Get total count
        response = await recipe_client_e2e.get("/api/recipes/")
        total = response.json()["total"]
        assert total == 25

        # Page through all recipes
        page_size = 10
        all_recipes = []
        offset = 0

        while offset < total:
            response = await recipe_client_e2e.get(f"/api/recipes/?limit={page_size}&offset={offset}")
            assert response.status_code == 200
            page_recipes = response.json()["recipes"]
            all_recipes.extend(page_recipes)
            offset += page_size

        # Verify we got all recipes with no duplicates
        recipe_ids = [r["recipe_id"] for r in all_recipes]
        assert len(recipe_ids) == 25
        assert len(set(recipe_ids)) == 25  # All unique


@pytest.mark.asyncio
class TestRecipeValidationScenarios:
    """Test various validation scenarios."""

    async def test_reject_circular_dependencies(self, recipe_client_e2e):
        """Test that circular dependencies are prevented."""
        # Note: Our validator prevents forward dependencies, which makes
        # circular dependencies impossible, but let's test the forward dep check
        recipe = {
            "name": "circular-test",
            "description": "Test",
            "version": "1.0.0",
            "recipe_data": {
                "name": "circular-test",
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
                        "depends_on": ["step2"],  # Forward dependency
                    },
                    {
                        "id": "step2",
                        "type": "bash",
                        "command": "test",
                        "timeout": 30,
                    },
                ],
            },
        }

        response = await recipe_client_e2e.post("/api/recipes/", json=recipe)
        assert response.status_code == 422  # Pydantic validation error
        detail = response.json()["detail"]
        assert any("not defined in a previous step" in str(d) for d in detail)

    async def test_valid_complex_dependency_graph(self, recipe_client_e2e):
        """Test that complex but valid dependency graphs work."""
        recipe = {
            "name": "complex-deps",
            "description": "Complex dependency graph",
            "version": "1.0.0",
            "recipe_data": {
                "name": "complex-deps",
                "description": "Complex dependency graph",
                "version": "1.0.0",
                "author": "test@example.com",
                "tags": [],
                "context": {},
                "steps": [
                    {"id": "a", "type": "bash", "command": "test", "timeout": 30},
                    {"id": "b", "type": "bash", "command": "test", "timeout": 30},
                    {
                        "id": "c",
                        "type": "bash",
                        "command": "test",
                        "timeout": 30,
                        "depends_on": ["a"],
                    },
                    {
                        "id": "d",
                        "type": "bash",
                        "command": "test",
                        "timeout": 30,
                        "depends_on": ["a", "b"],
                    },
                    {
                        "id": "e",
                        "type": "bash",
                        "command": "test",
                        "timeout": 30,
                        "depends_on": ["c", "d"],
                    },
                ],
            },
        }

        response = await recipe_client_e2e.post("/api/recipes/", json=recipe)
        assert response.status_code == 201


@pytest.mark.asyncio
class TestRecipeMetadataOperations:
    """Test operations on recipe metadata."""

    async def test_update_only_metadata_not_data(self, recipe_client_e2e):
        """Test updating only metadata fields without touching recipe_data."""
        # Create recipe
        base_recipe_data = {
            "name": "meta-test",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [{"id": "step1", "type": "bash", "command": "test", "timeout": 30}],
        }

        create_payload = {
            "name": "meta-test",
            "description": "Original description",
            "version": "1.0.0",
            "recipe_data": base_recipe_data,
            "tags": {"old": "tag"},
        }

        create_response = await recipe_client_e2e.post("/api/recipes/", json=create_payload)
        recipe_id = create_response.json()["recipe_id"]
        original_data = create_response.json()["recipe_data"]

        # Update only metadata
        update_payload = {
            "description": "Updated description",
            "tags": {"new": "tag", "added": "value"},
        }

        update_response = await recipe_client_e2e.put(
            f"/api/recipes/{recipe_id}", json=update_payload
        )
        assert update_response.status_code == 200

        updated = update_response.json()
        assert updated["description"] == "Updated description"
        assert updated["tags"] == {"new": "tag", "added": "value"}
        # recipe_data should be unchanged
        assert updated["recipe_data"] == original_data

    async def test_retrieve_only_metadata_via_list(self, recipe_client_e2e):
        """Test that list endpoint returns metadata only (no recipe_data)."""
        # Create a recipe with large recipe_data
        base_recipe_data = {
            "name": "large-recipe",
            "description": "Test",
            "version": "1.0.0",
            "author": "test@example.com",
            "tags": [],
            "context": {},
            "steps": [{"id": f"step{i}", "type": "bash", "command": "test", "timeout": 30} for i in range(20)],
        }

        create_payload = {
            "name": "large-recipe",
            "description": "A recipe with many steps",
            "version": "1.0.0",
            "recipe_data": base_recipe_data,
        }

        await recipe_client_e2e.post("/api/recipes/", json=create_payload)

        # List recipes
        list_response = await recipe_client_e2e.get("/api/recipes/")
        recipes = list_response.json()["recipes"]

        # Verify metadata only (no recipe_data)
        for recipe in recipes:
            assert "recipe_id" in recipe
            assert "name" in recipe
            assert "description" in recipe
            assert "version" in recipe
            assert "recipe_data" not in recipe  # Should NOT be in list response
