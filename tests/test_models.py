"""Tests for Pydantic data models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from amplifier_app_api.models import (
    BundleAddRequest,
    MessageRequest,
    ProviderConfigRequest,
    Session,
    SessionCreateRequest,
    SessionMetadata,
    SessionStatus,
    ToolInvokeRequest,
)


class TestSessionModels:
    """Test session data models."""

    def test_session_metadata_defaults(self):
        """Test SessionMetadata with defaults."""
        meta = SessionMetadata()
        assert meta.message_count == 0
        assert isinstance(meta.tags, dict)
        assert isinstance(meta.created_at, datetime)

    def test_session_metadata_with_values(self):
        """Test SessionMetadata with values."""
        meta = SessionMetadata(
            bundle="foundation",
            provider="anthropic",
            model="claude-sonnet-4-5",
            message_count=5,
        )
        assert meta.bundle == "foundation"
        assert meta.provider == "anthropic"
        assert meta.message_count == 5

    def test_session_status_enum(self):
        """Test SessionStatus enum values."""
        assert SessionStatus.ACTIVE.value == "active"
        assert SessionStatus.COMPLETED.value == "completed"
        assert SessionStatus.FAILED.value == "failed"
        assert SessionStatus.CANCELLED.value == "cancelled"

    def test_session_full_model(self):
        """Test complete Session model."""
        session = Session(
            session_id="test-123",
            status=SessionStatus.ACTIVE,
            metadata=SessionMetadata(bundle="foundation"),
        )
        assert session.session_id == "test-123"
        assert session.status == SessionStatus.ACTIVE
        assert session.metadata.bundle == "foundation"

    def test_session_with_transcript(self):
        """Test Session with transcript."""
        session = Session(
            session_id="test-123",
            transcript=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
            ],
        )
        assert len(session.transcript) == 2
        assert session.transcript[0]["role"] == "user"


class TestRequestModels:
    """Test request models validation."""

    def test_session_create_request_minimal(self):
        """Test SessionCreateRequest with minimal data."""
        request = SessionCreateRequest()
        assert request.bundle is None
        assert request.provider is None
        assert isinstance(request.config, dict)

    def test_session_create_request_full(self):
        """Test SessionCreateRequest with all fields."""
        request = SessionCreateRequest(
            bundle="foundation",
            provider="anthropic",
            model="claude-sonnet-4-5",
            config={"debug": True},
            metadata={"project": "test"},
        )
        assert request.bundle == "foundation"
        assert request.config["debug"] is True

    def test_message_request_valid(self):
        """Test MessageRequest with valid data."""
        request = MessageRequest(message="Hello")
        assert request.message == "Hello"
        assert isinstance(request.context, dict)

    def test_message_request_missing_message(self):
        """Test MessageRequest missing required field."""
        with pytest.raises(ValidationError):
            MessageRequest()

    def test_message_request_with_context(self):
        """Test MessageRequest with context."""
        request = MessageRequest(
            message="Test",
            context={"file": "test.py", "line": 10},
        )
        assert request.context["file"] == "test.py"

    def test_provider_config_request_minimal(self):
        """Test ProviderConfigRequest minimal."""
        request = ProviderConfigRequest(provider="anthropic")
        assert request.provider == "anthropic"
        assert request.scope == "global"

    def test_provider_config_request_with_api_key(self):
        """Test ProviderConfigRequest with API key."""
        request = ProviderConfigRequest(
            provider="anthropic",
            api_key="sk-test-key",
        )
        assert request.api_key == "sk-test-key"

    def test_provider_config_request_missing_provider(self):
        """Test ProviderConfigRequest without provider name."""
        with pytest.raises(ValidationError):
            ProviderConfigRequest()

    def test_bundle_add_request_minimal(self):
        """Test BundleAddRequest with minimal data."""
        request = BundleAddRequest(source="git+https://example.com/bundle")
        assert request.source == "git+https://example.com/bundle"
        assert request.scope == "global"

    def test_bundle_add_request_missing_source(self):
        """Test BundleAddRequest without source."""
        with pytest.raises(ValidationError):
            BundleAddRequest()

    def test_tool_invoke_request_valid(self):
        """Test ToolInvokeRequest with valid data."""
        request = ToolInvokeRequest(
            tool_name="read_file",
            parameters={"file_path": "/tmp/test.txt"},
        )
        assert request.tool_name == "read_file"
        assert request.parameters["file_path"] == "/tmp/test.txt"

    def test_tool_invoke_request_missing_tool_name(self):
        """Test ToolInvokeRequest without tool name."""
        with pytest.raises(ValidationError):
            ToolInvokeRequest(parameters={})


class TestModelSerialization:
    """Test model serialization and deserialization."""

    def test_session_to_dict(self):
        """Test Session serialization to dict."""
        session = Session(
            session_id="test-123",
            status=SessionStatus.ACTIVE,
        )
        data = session.model_dump()
        assert data["session_id"] == "test-123"
        assert data["status"] == "active"

    def test_session_from_dict(self):
        """Test Session deserialization from dict."""
        data = {
            "session_id": "test-123",
            "status": "active",
            "metadata": {
                "bundle": "foundation",
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
                "message_count": 0,
                "tags": {},
            },
            "transcript": [],
            "config": {},
        }
        session = Session(**data)
        assert session.session_id == "test-123"

    def test_session_json_serialization(self):
        """Test Session JSON serialization."""
        session = Session(session_id="test-123")
        json_str = session.model_dump_json()
        assert "test-123" in json_str
        assert isinstance(json_str, str)


class TestModelValidation:
    """Test model validation rules."""

    def test_session_id_required(self):
        """Test session_id is required."""
        with pytest.raises(ValidationError):
            Session()

    def test_session_invalid_status(self):
        """Test invalid status value rejected."""
        with pytest.raises(ValidationError):
            Session(session_id="test", status="invalid-status")

    def test_message_empty_string_allowed(self):
        """Test empty message string is allowed (validation at API layer)."""
        request = MessageRequest(message="")
        assert request.message == ""

    def test_config_dict_types(self):
        """Test config fields accept proper dict types."""
        request = SessionCreateRequest(
            config={"key": "value", "nested": {"a": 1}},
            metadata={"tag1": "value1"},
        )
        assert request.config["nested"]["a"] == 1
        assert request.metadata["tag1"] == "value1"
