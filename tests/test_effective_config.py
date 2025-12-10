"""Tests for effective_config module."""

import pytest
from unittest.mock import patch
from amplifier_foundation.effective_config import (
    EffectiveConfigSummary,
    get_effective_config_summary,
    _select_provider_by_priority,
    _get_provider_display_name,
)


def test_effective_config_summary_format_banner_line():
    """Test formatting config summary as banner line."""
    summary = EffectiveConfigSummary(
        profile="dev",
        provider_name="Anthropic",
        provider_module="provider-anthropic",
        model="claude-3-5-sonnet-20241022",
        orchestrator="loop-basic",
        tool_count=5,
        hook_count=2,
    )
    
    banner = summary.format_banner_line()
    
    assert "Profile: dev" in banner
    assert "Provider: Anthropic" in banner
    assert "claude-3-5-sonnet-20241022" in banner


def test_get_effective_config_summary_with_provider():
    """Test extracting config summary with provider."""
    config = {
        "providers": [
            {
                "module": "provider-anthropic",
                "config": {
                    "default_model": "claude-3-5-sonnet-20241022",
                    "priority": 1,
                }
            }
        ],
        "session": {
            "orchestrator": "loop-basic"
        },
        "tools": [{"module": "tool-1"}, {"module": "tool-2"}],
        "hooks": [{"module": "hook-1"}],
    }
    
    summary = get_effective_config_summary(config, "dev")
    
    assert summary.profile == "dev"
    assert summary.provider_module == "provider-anthropic"
    assert summary.model == "claude-3-5-sonnet-20241022"
    assert summary.orchestrator == "loop-basic"
    assert summary.tool_count == 2
    assert summary.hook_count == 1


def test_get_effective_config_summary_no_provider():
    """Test extracting config summary without provider."""
    config = {
        "session": {"orchestrator": "loop-basic"},
        "tools": [],
        "hooks": [],
    }
    
    summary = get_effective_config_summary(config, "default")
    
    assert summary.profile == "default"
    assert summary.provider_module == "none"
    assert summary.provider_name == "None"
    assert summary.model == "none"


def test_get_effective_config_summary_orchestrator_as_dict():
    """Test extracting config when orchestrator is a dict."""
    config = {
        "session": {
            "orchestrator": {"module": "loop-advanced"}
        },
        "tools": [],
        "hooks": [],
    }
    
    summary = get_effective_config_summary(config, "default")
    
    assert summary.orchestrator == "loop-advanced"


def test_select_provider_by_priority_single():
    """Test selecting provider when only one exists."""
    providers = [
        {"module": "provider-test", "config": {"priority": 10}}
    ]
    
    selected = _select_provider_by_priority(providers)
    
    assert selected["module"] == "provider-test"


def test_select_provider_by_priority_multiple():
    """Test selecting provider with lowest priority number."""
    providers = [
        {"module": "provider-low", "config": {"priority": 1}},
        {"module": "provider-high", "config": {"priority": 100}},
        {"module": "provider-mid", "config": {"priority": 50}},
    ]
    
    selected = _select_provider_by_priority(providers)
    
    # Should select provider-low (priority 1)
    assert selected["module"] == "provider-low"


def test_select_provider_by_priority_default():
    """Test selecting provider when priority not specified."""
    providers = [
        {"module": "provider-explicit", "config": {"priority": 50}},
        {"module": "provider-default", "config": {}},  # No priority = 100
    ]
    
    selected = _select_provider_by_priority(providers)
    
    # Should select provider-explicit (priority 50 beats default 100)
    assert selected["module"] == "provider-explicit"


def test_select_provider_by_priority_empty():
    """Test selecting provider from empty list."""
    providers = []
    
    selected = _select_provider_by_priority(providers)
    
    assert selected is None


def test_select_provider_by_priority_invalid_entries():
    """Test selecting provider with invalid entries."""
    providers = [
        "invalid-string",
        {"module": "provider-valid", "config": {"priority": 10}},
        None,
    ]
    
    selected = _select_provider_by_priority(providers)
    
    # Should skip invalid entries and select valid one
    assert selected["module"] == "provider-valid"


@patch("amplifier_foundation.effective_config.get_provider_info")
def test_get_provider_display_name_from_info(mock_get_info):
    """Test getting provider display name from provider info."""
    mock_get_info.return_value = {"display_name": "Custom Provider Name"}
    
    name = _get_provider_display_name("provider-test")
    
    assert name == "Custom Provider Name"
    mock_get_info.assert_called_once_with("provider-test")


@patch("amplifier_foundation.effective_config.get_provider_info")
def test_get_provider_display_name_known_providers(mock_get_info):
    """Test getting display name for known providers."""
    mock_get_info.return_value = None
    
    # Test known provider mappings
    assert _get_provider_display_name("provider-anthropic") == "Anthropic"
    assert _get_provider_display_name("provider-openai") == "OpenAI"
    assert _get_provider_display_name("provider-azure-openai") == "Azure OpenAI"
    assert _get_provider_display_name("provider-ollama") == "Ollama"
    assert _get_provider_display_name("provider-vllm") == "vLLM"


@patch("amplifier_foundation.effective_config.get_provider_info")
def test_get_provider_display_name_fallback(mock_get_info):
    """Test getting display name with fallback conversion."""
    mock_get_info.return_value = None
    
    name = _get_provider_display_name("provider-custom-ai")
    
    # Should convert to title case
    assert name == "Custom Ai"


@patch("amplifier_foundation.effective_config.get_provider_info")
def test_get_provider_display_name_exception(mock_get_info):
    """Test getting display name when get_provider_info raises exception."""
    mock_get_info.side_effect = Exception("Provider not found")
    
    # Should fall back to name mapping
    name = _get_provider_display_name("provider-anthropic")
    
    assert name == "Anthropic"
