# Recipe System Documentation

## Overview

The Recipe System provides a robust way to store, manage, and execute long-running tasks (recipes) with multiple steps. Each recipe is user-scoped, validated before storage, and stored as JSON in PostgreSQL.

## Table of Contents

- [Architecture](#architecture)
- [Data Model](#data-model)
- [Recipe Structure](#recipe-structure)
- [API Endpoints](#api-endpoints)
- [Validation Rules](#validation-rules)
- [Error Handling](#error-handling)
- [Examples](#examples)
- [Best Practices](#best-practices)

## Architecture

```
┌─────────────────┐
│   API Layer     │  REST endpoints (recipes.py)
└────────┬────────┘
         │
┌────────▼────────┐
│ Business Logic  │  RecipeManager (recipe_manager.py)
└────────┬────────┘
         │
┌────────▼────────┐
│   Validation    │  Recipe validator (validators/recipe.py)
└────────┬────────┘
         │
┌────────▼────────┐
│  Data Layer     │  Database operations (database.py)
└────────┬────────┘
         │
┌────────▼────────┐
│   PostgreSQL    │  JSONB storage with indexes
└─────────────────┘
```

## Data Model

### Database Schema

```sql
CREATE TABLE recipes (
    recipe_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    version VARCHAR(50) NOT NULL DEFAULT '1.0.0',
    recipe_data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tags JSONB DEFAULT '{}'::jsonb,
    UNIQUE(user_id, name)
);
```

### Pydantic Models

#### Recipe
Complete recipe with all fields.

```python
class Recipe(BaseModel):
    recipe_id: str
    name: str
    description: str | None
    version: str
    recipe_data: dict[str, Any]
    user_id: str
    created_at: datetime
    updated_at: datetime
    tags: dict[str, str]
```

#### RecipeMetadata
Lightweight version without recipe_data (for list operations).

```python
class RecipeMetadata(BaseModel):
    recipe_id: str
    name: str
    description: str | None
    version: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    tags: dict[str, str]
```

## Recipe Structure

Based on the [amplifier-foundation recipe schema](https://github.com/microsoft/amplifier-foundation/blob/main/recipes/validate-bundle.yaml).

### Required Top-Level Fields

```json
{
  "name": "string",
  "description": "string",
  "version": "string (semver)",
  "author": "string",
  "tags": ["array", "of", "strings"],
  "context": {
    "param_name": "description"
  },
  "steps": [...]
}
```

### Step Structure

Each step must include:

```json
{
  "id": "unique-step-id",
  "type": "bash|recipe|agent",
  "timeout": 30,
  "depends_on": ["optional-step-id"]
}
```

#### Step Types

**Bash Step**
```json
{
  "id": "run-tests",
  "type": "bash",
  "command": "pytest tests/",
  "timeout": 300
}
```

**Recipe Step** (nested recipe execution)
```json
{
  "id": "sub-recipe",
  "type": "recipe",
  "recipe": "recipes:common/setup.yaml",
  "context": {"env": "production"},
  "timeout": 600
}
```

**Agent Step** (AI agent execution)
```json
{
  "id": "analyze",
  "type": "agent",
  "agent": "code-reviewer",
  "prompt": "Review the changes in src/",
  "mode": "review",
  "timeout": 120
}
```

## API Endpoints

### Create Recipe

**POST** `/api/recipes`

Creates a new recipe. Validates structure before saving.

**Request Body:**
```json
{
  "name": "deploy-production",
  "description": "Deploy to production environment",
  "version": "1.0.0",
  "recipe_data": {
    "name": "deploy-production",
    "description": "Deploy to production",
    "version": "1.0.0",
    "author": "user@example.com",
    "tags": ["deployment", "production"],
    "context": {
      "environment": "production environment name"
    },
    "steps": [
      {
        "id": "run-tests",
        "type": "bash",
        "command": "pytest tests/",
        "timeout": 300
      },
      {
        "id": "deploy",
        "type": "bash",
        "command": "kubectl apply -f k8s/",
        "timeout": 600,
        "depends_on": ["run-tests"]
      }
    ]
  },
  "tags": {
    "category": "deployment",
    "environment": "production"
  }
}
```

**Response (201):**
```json
{
  "recipe_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "deploy-production",
  "description": "Deploy to production environment",
  "version": "1.0.0",
  "recipe_data": {...},
  "user_id": "user123",
  "created_at": "2026-02-11T10:00:00Z",
  "updated_at": "2026-02-11T10:00:00Z",
  "tags": {"category": "deployment"},
  "message": "Recipe created successfully"
}
```

### List Recipes

**GET** `/api/recipes`

Lists all recipes for the authenticated user.

**Query Parameters:**
- `tags` (optional): Filter by tags (comma-separated `key:value` pairs)
- `limit` (optional, default=50): Max results
- `offset` (optional, default=0): Pagination offset

**Examples:**
```bash
# List all recipes
GET /api/recipes

# Filter by tag
GET /api/recipes?tags=category:deployment

# Multiple tag filters
GET /api/recipes?tags=category:deployment,environment:production

# Pagination
GET /api/recipes?limit=10&offset=20
```

**Response (200):**
```json
{
  "recipes": [
    {
      "recipe_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "deploy-production",
      "description": "Deploy to production environment",
      "version": "1.0.0",
      "user_id": "user123",
      "created_at": "2026-02-11T10:00:00Z",
      "updated_at": "2026-02-11T10:00:00Z",
      "tags": {"category": "deployment"}
    }
  ],
  "total": 1
}
```

### Get Recipe

**GET** `/api/recipes/{recipe_id}`

Retrieves a specific recipe by ID.

**Response (200):**
```json
{
  "recipe_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "deploy-production",
  "version": "1.0.0",
  "recipe_data": {...},
  "user_id": "user123",
  "created_at": "2026-02-11T10:00:00Z",
  "updated_at": "2026-02-11T10:00:00Z",
  "tags": {"category": "deployment"}
}
```

### Update Recipe

**PUT** `/api/recipes/{recipe_id}`

Updates an existing recipe. All fields are optional.

**Request Body:**
```json
{
  "description": "Updated description",
  "version": "1.1.0",
  "tags": {
    "category": "deployment",
    "reviewed": "true"
  }
}
```

**Response (200):**
```json
{
  "recipe_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "deploy-production",
  "description": "Updated description",
  "version": "1.1.0",
  "recipe_data": {...},
  "user_id": "user123",
  "created_at": "2026-02-11T10:00:00Z",
  "updated_at": "2026-02-11T10:15:00Z",
  "tags": {"category": "deployment", "reviewed": "true"},
  "message": "Recipe updated successfully"
}
```

### Delete Recipe

**DELETE** `/api/recipes/{recipe_id}`

Deletes a recipe.

**Response (204):** No content

## Validation Rules

### Pre-Save Validation

All recipes are validated **before** being saved to the database. Once stored, the system assumes they are safe to execute.

### Required Fields

- `name`: Non-empty string
- `description`: String
- `version`: String (e.g., "1.0.0")
- `author`: String
- `tags`: Array
- `context`: Object
- `steps`: Non-empty array

### Step Validation

1. **Required Fields:** `id`, `type`, `timeout`
2. **Unique IDs:** Step IDs must be unique within the recipe
3. **Positive Timeout:** Must be > 0
4. **depends_on (optional):**
   - Must be an array
   - Can only reference steps defined **earlier** in the steps array
   - Prevents circular dependencies

### Type-Specific Validation

- **bash:** Must have `command` field
- **recipe:** Must have `recipe` field
- **agent:** Must have both `agent` and `prompt` fields

## Error Handling

### Validation Errors (400)

```json
{
  "detail": "Recipe validation failed: Step 2 ('deploy'): depends on 'build' which is not defined in a previous step"
}
```

### Not Found (404)

```json
{
  "detail": "Recipe not found"
}
```

### Server Errors (500)

```json
{
  "detail": "Failed to create recipe: Database connection failed"
}
```

## Examples

### Simple Bash Recipe

```json
{
  "name": "run-tests",
  "description": "Run test suite",
  "version": "1.0.0",
  "recipe_data": {
    "name": "run-tests",
    "description": "Run test suite",
    "version": "1.0.0",
    "author": "devops@example.com",
    "tags": ["testing", "ci"],
    "context": {},
    "steps": [
      {
        "id": "unit-tests",
        "type": "bash",
        "command": "pytest tests/unit",
        "timeout": 300
      },
      {
        "id": "integration-tests",
        "type": "bash",
        "command": "pytest tests/integration",
        "timeout": 600,
        "depends_on": ["unit-tests"]
      }
    ]
  }
}
```

### Multi-Step Deployment

```json
{
  "name": "full-deployment",
  "description": "Complete deployment pipeline",
  "version": "2.0.0",
  "recipe_data": {
    "name": "full-deployment",
    "description": "Complete deployment pipeline",
    "version": "2.0.0",
    "author": "platform@example.com",
    "tags": ["deployment", "production", "pipeline"],
    "context": {
      "environment": "Target environment (staging/production)",
      "version": "Version to deploy"
    },
    "steps": [
      {
        "id": "validate-env",
        "type": "bash",
        "command": "validate-environment.sh ${environment}",
        "timeout": 60
      },
      {
        "id": "run-tests",
        "type": "recipe",
        "recipe": "recipes:common/test-suite.yaml",
        "timeout": 900,
        "depends_on": ["validate-env"]
      },
      {
        "id": "build-artifacts",
        "type": "bash",
        "command": "build.sh ${version}",
        "timeout": 600,
        "depends_on": ["run-tests"]
      },
      {
        "id": "deploy-services",
        "type": "bash",
        "command": "kubectl apply -f k8s/${environment}/",
        "timeout": 300,
        "depends_on": ["build-artifacts"]
      },
      {
        "id": "health-check",
        "type": "agent",
        "agent": "health-checker",
        "prompt": "Verify all services are healthy in ${environment}",
        "timeout": 120,
        "depends_on": ["deploy-services"]
      }
    ]
  },
  "tags": {
    "category": "deployment",
    "criticality": "high"
  }
}
```

### Agent-Based Code Review

```json
{
  "name": "code-review-pipeline",
  "description": "Automated code review workflow",
  "version": "1.0.0",
  "recipe_data": {
    "name": "code-review-pipeline",
    "description": "Automated code review workflow",
    "version": "1.0.0",
    "author": "quality@example.com",
    "tags": ["review", "quality", "automation"],
    "context": {
      "pr_number": "Pull request number to review"
    },
    "steps": [
      {
        "id": "fetch-changes",
        "type": "bash",
        "command": "gh pr diff ${pr_number} > changes.diff",
        "timeout": 30
      },
      {
        "id": "static-analysis",
        "type": "bash",
        "command": "pylint src/",
        "timeout": 120,
        "depends_on": ["fetch-changes"]
      },
      {
        "id": "ai-review",
        "type": "agent",
        "agent": "code-reviewer",
        "prompt": "Review the changes in changes.diff for potential issues",
        "mode": "review",
        "timeout": 300,
        "depends_on": ["static-analysis"]
      },
      {
        "id": "post-comment",
        "type": "bash",
        "command": "gh pr comment ${pr_number} --body-file review-results.md",
        "timeout": 30,
        "depends_on": ["ai-review"]
      }
    ]
  },
  "tags": {
    "category": "automation",
    "type": "review"
  }
}
```

## Best Practices

### Naming Conventions

- **Recipe names:** Use kebab-case: `deploy-production`, `run-tests`
- **Step IDs:** Use kebab-case: `build-artifacts`, `health-check`
- **Versions:** Follow semantic versioning: `1.0.0`, `2.1.3`

### Timeouts

- Set realistic timeouts based on expected execution time
- Add buffer for network delays and resource contention
- Short tasks: 30-60 seconds
- Build/compile: 5-10 minutes
- Deployments: 5-15 minutes
- Long-running analysis: 30+ minutes

### Dependencies

- Order steps logically (earlier steps should be prerequisites)
- Minimize dependencies for better parallelization
- Use `depends_on` to enforce execution order
- Avoid circular dependencies (validator prevents this)

### Tags

Use tags for:
- **Category:** `category:deployment`, `category:testing`
- **Environment:** `environment:production`, `environment:staging`
- **Team ownership:** `team:platform`, `team:data`
- **Criticality:** `criticality:high`, `criticality:low`

### Versioning

- Increment patch version (1.0.X) for bug fixes
- Increment minor version (1.X.0) for new steps
- Increment major version (X.0.0) for breaking changes
- Keep old versions for rollback capability

### Error Handling

- Validate recipes before deployment
- Test recipes in staging before production
- Monitor recipe execution via telemetry
- Set appropriate timeouts to prevent hanging

### Security

- **Never hardcode secrets** in recipe_data
- Use parameter substitution: `${api_key}`
- Store secrets in secure vaults
- Pass secrets at execution time, not creation time

### Performance

- Use tag filters to narrow searches
- Limit results with pagination
- Cache frequently-used recipes client-side
- Index tags for fast filtering

## Telemetry Events

The recipe system emits the following telemetry events:

- **recipe.created:** When a recipe is created
  - `recipe_id`, `user_id`, `name`, `version`, `step_count`
- **recipe.updated:** When a recipe is updated
  - `recipe_id`, `user_id`, `fields_updated`
- **recipe.deleted:** When a recipe is deleted
  - `recipe_id`, `user_id`

## Future Enhancements

Potential features for future versions:

1. **Recipe Execution Engine:** Execute recipes directly via API
2. **Version History:** Track all versions of a recipe
3. **Recipe Templates:** Pre-built templates for common tasks
4. **Access Control:** Share recipes with teams/organizations
5. **Execution History:** Track recipe execution results
6. **Step Output Capture:** Store and retrieve step outputs
7. **Conditional Steps:** Execute steps based on conditions
8. **Parallel Execution:** Run independent steps concurrently
9. **Retry Logic:** Automatic retry on transient failures
10. **Notifications:** Alert on recipe completion/failure

## Support

For issues, questions, or feature requests:
- GitHub Issues: [amplifier-app-api/issues](https://github.com/yourusername/amplifier-app-api/issues)
- Documentation: [docs/](../docs/)
- API Reference: `/docs` (when service is running)
