"""Tests for session store."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from amplifier_app_utils.session_store import SessionStore


@pytest.fixture
def temp_session_dir(tmp_path):
    """Create temporary directory for session storage."""
    return tmp_path / "sessions"


@pytest.fixture
def session_store(temp_session_dir):
    """Create session store with temporary directory."""
    return SessionStore(base_dir=temp_session_dir)


def test_session_store_init(session_store, temp_session_dir):
    """Test session store initialization."""
    assert session_store.base_dir == temp_session_dir
    assert temp_session_dir.exists()


def test_save_and_load_session(session_store):
    """Test saving and loading a session."""
    session_id = "test-session"
    transcript = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    metadata = {
        "session_id": session_id,
        "created": datetime.now(UTC).isoformat(),
    }

    # Save session
    session_store.save(session_id, transcript, metadata)

    # Session should exist
    assert session_store.exists(session_id)

    # Load session
    loaded_transcript, loaded_metadata = session_store.load(session_id)

    assert loaded_transcript == transcript
    assert loaded_metadata == metadata


def test_save_session_creates_directory(session_store):
    """Test that saving a session creates its directory."""
    session_id = "new-session"
    transcript = []
    metadata = {}

    session_store.save(session_id, transcript, metadata)

    session_dir = session_store.base_dir / session_id
    assert session_dir.exists()
    assert session_dir.is_dir()


def test_save_session_invalid_id(session_store):
    """Test that invalid session IDs are rejected."""
    with pytest.raises(ValueError, match="session_id cannot be empty"):
        session_store.save("", [], {})

    with pytest.raises(ValueError, match="Invalid session_id"):
        session_store.save("../evil", [], {})

    with pytest.raises(ValueError, match="Invalid session_id"):
        session_store.save("sub/dir", [], {})


def test_load_nonexistent_session(session_store):
    """Test loading a session that doesn't exist."""
    with pytest.raises(FileNotFoundError):
        session_store.load("nonexistent-session")


def test_exists_session(session_store):
    """Test checking if session exists."""
    assert not session_store.exists("nonexistent")

    # Create a session
    session_store.save("existing", [], {})

    assert session_store.exists("existing")
    assert not session_store.exists("nonexistent")


def test_list_sessions(session_store):
    """Test listing all sessions."""
    # Initially empty
    assert session_store.list_sessions() == []

    # Create multiple sessions
    session_store.save("session1", [], {})
    session_store.save("session2", [], {})
    session_store.save("session3", [], {})

    sessions = session_store.list_sessions()
    assert len(sessions) == 3
    assert "session1" in sessions
    assert "session2" in sessions
    assert "session3" in sessions


def test_list_sessions_sorted_by_mtime(session_store):
    """Test that sessions are sorted by modification time (newest first)."""
    import time

    # Create sessions with slight delays
    session_store.save("old-session", [], {})
    time.sleep(0.01)

    session_store.save("new-session", [], {})

    sessions = session_store.list_sessions()

    # Newest should be first
    assert sessions[0] == "new-session"
    assert sessions[1] == "old-session"


def test_sanitize_message_with_non_serializable(session_store):
    """Test that non-serializable objects are sanitized."""

    class NonSerializable:
        pass

    message = {
        "role": "user",
        "content": "Hello",
        "metadata": NonSerializable(),  # Non-serializable
        "thinking_block": {"text": "Thinking..."},  # Should be converted
    }

    sanitized = session_store._sanitize_message(message)

    # Basic fields should be preserved
    assert sanitized["role"] == "user"
    assert sanitized["content"] == "Hello"

    # Non-serializable should be removed
    assert "metadata" not in sanitized

    # thinking_block should be converted to thinking_text
    assert "thinking_text" in sanitized
    assert sanitized["thinking_text"] == "Thinking..."


def test_save_session_filters_system_messages(session_store):
    """Test that system and developer messages are filtered from transcript."""
    session_id = "test-filtering"
    transcript = [
        {"role": "system", "content": "System instruction"},
        {"role": "developer", "content": "Context file"},
        {"role": "user", "content": "User message"},
        {"role": "assistant", "content": "Assistant reply"},
    ]
    metadata = {}

    session_store.save(session_id, transcript, metadata)

    # Load and check
    loaded_transcript, _ = session_store.load(session_id)

    # Should only have user and assistant messages
    assert len(loaded_transcript) == 2
    assert loaded_transcript[0]["role"] == "user"
    assert loaded_transcript[1]["role"] == "assistant"


def test_save_profile(session_store):
    """Test saving profile snapshot."""
    session_id = "test-profile"
    profile = {
        "name": "test-profile",
        "providers": ["provider-anthropic"],
        "tools": ["tool-search"],
    }

    # Create session first
    session_store.save(session_id, [], {})

    # Save profile
    session_store.save_profile(session_id, profile)

    # Check file exists
    profile_file = session_store.base_dir / session_id / "profile.md"
    assert profile_file.exists()


def test_cleanup_old_sessions(session_store):
    """Test cleanup of old sessions."""
    import time

    # Create a session
    session_store.save("old-session", [], {})

    # Modify the timestamp to make it old
    session_dir = session_store.base_dir / "old-session"
    old_time = time.time() - (31 * 24 * 60 * 60)  # 31 days ago
    os.utime(session_dir, (old_time, old_time))

    # Create a recent session
    session_store.save("recent-session", [], {})

    # Cleanup sessions older than 30 days
    removed = session_store.cleanup_old_sessions(days=30)

    # Should have removed 1 session
    assert removed == 1

    # Old session should be gone, recent should remain
    assert not session_store.exists("old-session")
    assert session_store.exists("recent-session")


# Add os import for the cleanup test
import os
