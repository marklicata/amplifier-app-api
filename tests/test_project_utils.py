"""Tests for project utilities."""

import pytest
from pathlib import Path

from amplifier_app_utils.project_utils import get_project_slug


def test_get_project_slug():
    """Test project slug generation."""
    slug = get_project_slug()

    # Should be a string
    assert isinstance(slug, str)

    # Should start with hyphen
    assert slug.startswith("-")

    # Should not contain path separators
    assert "/" not in slug
    assert "\\" not in slug

    # Should not contain colons (Windows drive letters)
    assert ":" not in slug

    # Should be deterministic (same directory = same slug)
    slug2 = get_project_slug()
    assert slug == slug2


def test_get_project_slug_contains_cwd():
    """Test that slug contains some part of the current directory."""
    slug = get_project_slug()
    cwd = Path.cwd()

    # Get the last directory name (should be in slug)
    last_dir = cwd.name.lower()

    # Should contain the last directory name (or sanitized version)
    assert last_dir.replace("-", "") in slug.replace("-", "")
