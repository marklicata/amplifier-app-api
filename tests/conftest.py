"""Pytest configuration and fixtures."""

import os
from pathlib import Path
from unittest.mock import AsyncMock, Mock

# Set test environment variables BEFORE importing anything that loads settings
# This ensures tests run with auth disabled by default and use HS256 for JWTs
os.environ["AUTH_REQUIRED"] = "false"
os.environ["JWT_ALGORITHM"] = "HS256"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Force reload of settings with test environment
import amplifier_app_api.config as config_module

config_module.settings = config_module.Settings()

# Verify settings are correct for tests
assert config_module.settings.auth_required is False, (
    "Test setup failed: auth_required should be False"
)
assert config_module.settings.jwt_algorithm == "HS256", (
    "Test setup failed: jwt_algorithm should be HS256"
)


@pytest.fixture
def anyio_backend():
    """Use asyncio backend for async tests."""
    return "asyncio"


@pytest.fixture
def enable_auth():
    """Context manager to enable authentication for a test.

    Usage:
        with enable_auth:
            response = await client.get("/sessions")
    """
    from amplifier_app_api.config import settings

    class AuthEnabler:
        def __enter__(self):
            # Use object.__setattr__ to bypass Pydantic's immutability
            object.__setattr__(settings, "auth_required", True)
            return self

        def __exit__(self, *args):
            object.__setattr__(settings, "auth_required", False)

    return AuthEnabler()


@pytest_asyncio.fixture(scope="function")
async def test_db():
    """Create a test database for each test.

    Note: This connects to the actual PostgreSQL database configured in .env
    Tests will use real Azure PostgreSQL but with test data that gets cleaned up.
    """
    from amplifier_app_api.config import settings
    from amplifier_app_api.storage.database import Database

    # Use the configured database (should be Azure PostgreSQL test instance)
    db_url = settings.get_database_url()
    db = Database(db_url)
    await db.connect()

    yield db

    # Cleanup - delete any test data
    # (Tests should use predictable IDs like 'test-*' for cleanup)
    if db._pool:
        async with db._pool.acquire() as conn:
            await conn.execute("DELETE FROM sessions WHERE session_id LIKE 'test-%'")
            await conn.execute("DELETE FROM configs WHERE config_id LIKE 'test-%'")

    await db.disconnect()


@pytest.fixture(scope="function")
def mock_session_manager():
    """Create a mock session manager that doesn't load amplifier-core."""
    from amplifier_app_api.models import Session, SessionMetadata, SessionStatus

    manager = Mock()

    # Mock create_session with new signature (config_id, user_id, app_id)
    async def mock_create(config_id, user_id=None, app_id=None):
        session_id = "mock-session-123"
        return Session(
            session_id=session_id,
            config_id=config_id,
            status=SessionStatus.ACTIVE,
            metadata=SessionMetadata(
                config_id=config_id,
            ),
        )

    manager.create_session = AsyncMock(side_effect=mock_create)
    manager.get_session = AsyncMock(return_value=None)
    manager.list_sessions = AsyncMock(return_value=[])
    manager.delete_session = AsyncMock(return_value=True)
    manager.send_message = AsyncMock(
        return_value={
            "session_id": "mock-123",
            "response": "Mock response",
            "metadata": {"config_id": "mock-config-id"},
        }
    )
    manager.resume_session = AsyncMock(return_value=None)
    manager.get_amplifier_session = AsyncMock(return_value=None)
    manager.stream_message = AsyncMock(return_value=iter([]))  # Empty async generator
    manager.invalidate_config_cache = Mock()  # For cache invalidation

    return manager


@pytest.fixture(scope="function")
def mock_tool_manager():
    """Create a mock tool manager."""

    manager = Mock()

    # Mock get_tools_from_bundle
    async def mock_get_tools(bundle_name, load_bundle_func):
        return [
            {
                "name": "read_file",
                "description": "Read a file",
                "parameters": {},
                "has_execute": True,
            },
            {
                "name": "write_file",
                "description": "Write a file",
                "parameters": {},
                "has_execute": True,
            },
        ]

    manager.get_tools_from_bundle = AsyncMock(side_effect=mock_get_tools)

    # Mock invoke_tool
    async def mock_invoke(bundle_name, tool_name, parameters, load_bundle_func):
        return {"result": f"Mock result for {tool_name}"}

    manager.invoke_tool = AsyncMock(side_effect=mock_invoke)

    return manager


@pytest_asyncio.fixture(scope="function")
async def client(test_db, mock_session_manager, mock_tool_manager):
    """Create test client with all dependencies mocked."""
    from fastapi import FastAPI

    import amplifier_app_api.storage.database as db_module
    from amplifier_app_api.api import (
        applications_router,
        bundles,
        bundles_router,
        config_router,
        health_router,
        sessions,
        sessions_router,
        tools,
        tools_router,
    )
    from amplifier_app_api.api import config as config_api
    from amplifier_app_api.core import ConfigManager
    from amplifier_app_api.middleware.auth import AuthMiddleware
    from amplifier_app_api.storage.database import get_db

    # Create a test app with auth middleware
    test_app = FastAPI(title="Test App")

    # Add auth middleware so auth tests work
    test_app.add_middleware(AuthMiddleware)

    test_app.include_router(health_router)
    test_app.include_router(applications_router)
    test_app.include_router(sessions_router)
    test_app.include_router(config_router)
    test_app.include_router(bundles_router)
    test_app.include_router(tools_router)

    original_db = db_module._db
    db_module._db = test_db

    # Create real config manager with test db
    config_manager = ConfigManager(test_db)

    # Patch the ToolManager class to return our mock
    original_tool_manager = tools.ToolManager

    def mock_tool_manager_constructor():
        return mock_tool_manager

    tools.ToolManager = mock_tool_manager_constructor

    # Override dependencies
    test_app.dependency_overrides[get_db] = lambda: test_db
    test_app.dependency_overrides[sessions.get_session_manager] = lambda: mock_session_manager
    test_app.dependency_overrides[bundles.get_config_manager] = lambda: config_manager
    test_app.dependency_overrides[config_api.get_config_manager] = lambda: config_manager
    test_app.dependency_overrides[tools.get_session_manager] = lambda: mock_session_manager
    test_app.dependency_overrides[tools.get_config_manager] = lambda: config_manager

    # Auth is disabled by default (auth_required=False in settings)
    # Tests can enable it with patch.object(settings, "auth_required", True)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
            timeout=5.0,
        ) as test_client:
            yield test_client
    finally:
        # Cleanup
        test_app.dependency_overrides.clear()
        tools.ToolManager = original_tool_manager
        db_module._db = original_db


@pytest_asyncio.fixture(scope="function")
async def session_id(client):
    """Create a test session and return its ID."""
    # First create a config
    config_response = await client.post(
        "/configs",
        json={
            "name": "test-config",
            "yaml_content": """
bundle:
  name: test
includes:
  - bundle: foundation
session:
  orchestrator: loop-basic
  context: context-simple
providers:
  - module: provider-anthropic
    config:
      api_key: test-key
      model: claude-sonnet-4-5
""",
        },
    )
    if config_response.status_code != 200:
        return None

    config_id = config_response.json()["config_id"]

    # Then create session from config
    session_response = await client.post("/sessions", json={"config_id": config_id})
    if session_response.status_code == 201:
        return session_response.json()["session_id"]
    return None


@pytest.fixture(scope="module")
def live_service():
    """Use the already-running service for E2E tests.

    Checks if a service is running on common ports and uses it.
    This avoids the need to start a new service instance.
    """
    try:
        import httpx
    except ImportError:
        pytest.skip("httpx not installed - skipping E2E tests")

    # Check common ports for running service
    ports_to_check = [8765, 8767, 8000]
    base_url = None

    for port in ports_to_check:
        test_url = f"http://127.0.0.1:{port}"
        try:
            response = httpx.get(f"{test_url}/health", timeout=2.0)
            if response.status_code == 200:
                base_url = test_url
                print(f"\n✅ Found running service at {base_url}")
                break
        except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout):
            continue

    if not base_url:
        pytest.skip(
            "No running service found on ports 8765, 8767, or 8000. "
            "Start the service with './run-dev.sh' before running E2E tests."
        )

    # Verify database is connected
    try:
        health = httpx.get(f"{base_url}/health", timeout=5.0).json()
        if not health.get("database_connected"):
            pytest.skip(f"Service at {base_url} has no database connection")
    except Exception as e:
        pytest.skip(f"Cannot verify service health: {e}")

    yield base_url

    # No cleanup - we're using an existing service
    print(f"\n✓ E2E tests complete (used service at {base_url})")
