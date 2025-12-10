"""Tests for mention loading."""

import pytest
from amplifier_app_utils.mention_loading.utils import parse_mentions, extract_mention_path, has_mentions


def test_parse_mentions_basic():
    """Test basic @mention parsing."""
    mentions = parse_mentions("Check @file.md and @other.txt")
    assert "@file.md" in mentions
    assert "@other.txt" in mentions


def test_parse_mentions_collection():
    """Test collection @mention parsing."""
    mentions = parse_mentions("See @foundation:context/file.md")
    assert "@foundation:context/file.md" in mentions


def test_parse_mentions_excludes_code():
    """Test that code examples are excluded."""
    mentions = parse_mentions("Example: `@file.md`")
    assert len(mentions) == 0


def test_parse_mentions_excludes_quotes():
    """Test that quoted mentions are excluded."""
    mentions = parse_mentions('Example: "@file.md"')
    assert len(mentions) == 0


def test_has_mentions():
    """Test mention detection."""
    assert has_mentions("Check @file.md")
    assert not has_mentions("No mentions here")


def test_extract_mention_path():
    """Test path extraction."""
    assert extract_mention_path("@file.md") == "file.md"
    assert extract_mention_path("@path/to/file.md") == "path/to/file.md"


def test_parse_home_mentions():
    """Test home directory mentions."""
    mentions = parse_mentions("Check @~/.amplifier/file.md")
    assert "@~/.amplifier/file.md" in mentions
