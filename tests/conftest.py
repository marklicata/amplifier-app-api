"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def anyio_backend():
    """Use asyncio backend for async tests."""
    return "asyncio"


@pytest.fixture(scope="function")
async def test_db():
    """Create a test database for each test."""
    from amplifier_app_api.storage.database import Database

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db = Database(tmp.name)
        await db.connect()
        yield db
        await db.disconnect()
        # Cleanup
        Path(tmp.name).unlink(missing_ok=True)


@pytest.fixture(scope="function")
def mock_session_manager():
    """Create a mock session manager that doesn't load amplifier-core."""
    from amplifier_app_api.models import Session, SessionMetadata, SessionStatus

    manager = Mock()

    # Mock create_session (new signature: just config_id)
    async def mock_create(config_id):
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


@pytest.fixture(scope="function")
async def client(test_db, mock_session_manager, mock_tool_manager):
    """Create test client with all dependencies mocked."""
    # Set test database as global
    import amplifier_app_api.storage.database as db_module
    from amplifier_app_api.api import bundles, sessions, tools
    from amplifier_app_api.api import config as config_api
    from amplifier_app_api.core import ConfigManager
    from amplifier_app_api.main import app
    from amplifier_app_api.storage.database import get_db

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
    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[sessions.get_session_manager] = lambda: mock_session_manager
    app.dependency_overrides[bundles.get_config_manager] = lambda: config_manager
    app.dependency_overrides[config_api.get_config_manager] = lambda: config_manager
    app.dependency_overrides[tools.get_session_manager] = lambda: mock_session_manager
    app.dependency_overrides[tools.get_config_manager] = lambda: config_manager

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=5.0,  # 5 second timeout for test requests
        ) as test_client:
            yield test_client
    finally:
        # Cleanup
        app.dependency_overrides.clear()
        tools.ToolManager = original_tool_manager
        db_module._db = original_db


@pytest.fixture(scope="function")
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
    if session_response.status_code == 200:
        return session_response.json()["session_id"]
    return None
