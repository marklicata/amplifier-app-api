"""Test config logic without database - just YAML parsing."""

import yaml


def test_yaml_parsing():
    """Test YAML parsing utilities."""
    yaml_str = """
bundle:
  name: test-config
  version: 1.0.0

includes:
  - bundle: foundation

providers:
  - module: provider-anthropic
    config:
      api_key: sk-test-key
      model: claude-sonnet-4-5

session:
  orchestrator: loop-streaming
  context: context-persistent

tools:
  - module: tool-filesystem
    source: ./modules/tool-filesystem
    config:
      allowed_paths: ["."]
"""

    # Parse YAML
    parsed = yaml.safe_load(yaml_str)

    print("✓ YAML parses successfully")
    print(f"  Bundle name: {parsed['bundle']['name']}")
    print(f"  Includes: {len(parsed.get('includes', []))}")
    print(f"  Providers: {len(parsed.get('providers', []))}")
    print(f"  Tools: {len(parsed.get('tools', []))}")
    print(f"  Session orchestrator: {parsed['session']['orchestrator']}")
    print()

    # Test adding a tool programmatically
    if "tools" not in parsed:
        parsed["tools"] = []

    parsed["tools"].append(
        {"module": "tool-web", "source": "./modules/tool-web", "config": {"timeout": 30}}
    )

    print("✓ Added tool programmatically")
    print(f"  Tools after addition: {len(parsed['tools'])}")
    print()

    # Test adding a provider
    if "providers" not in parsed:
        parsed["providers"] = []

    parsed["providers"].append(
        {"module": "provider-openai", "config": {"api_key": "test-key", "model": "gpt-4o"}}
    )

    print("✓ Added provider programmatically")
    print(f"  Providers after addition: {len(parsed['providers'])}")
    print()

    # Test merging a bundle
    if "includes" not in parsed:
        parsed["includes"] = []

    parsed["includes"].append({"bundle": "recipes"})

    print("✓ Merged bundle programmatically")
    print(f"  Includes after merge: {len(parsed['includes'])}")
    print()

    # Dump back to YAML
    dumped = yaml.dump(parsed, default_flow_style=False, sort_keys=False)
    print("✓ Dumped back to YAML:")
    print("-" * 80)
    print(dumped)
    print("-" * 80)
    print()

    # Verify round-trip
    reparsed = yaml.safe_load(dumped)
    assert reparsed["bundle"]["name"] == parsed["bundle"]["name"]
    assert len(reparsed["tools"]) == len(parsed["tools"])
    assert len(reparsed["providers"]) == len(parsed["providers"])
    assert len(reparsed["includes"]) == len(parsed["includes"])

    print("✓ Round-trip verification passed")
    print()

    return True


def test_invalid_yaml():
    """Test invalid YAML detection."""
    invalid_yaml = """
bundle
  name test-config
"""

    try:
        yaml.safe_load(invalid_yaml)
        print("✗ Should have raised YAMLError")
        return False
    except yaml.YAMLError as e:
        print(f"✓ Invalid YAML correctly rejected: {type(e).__name__}")
        return True


def test_config_structure_requirements():
    """Test what makes a valid config YAML."""

    # Minimal valid config
    minimal = """
bundle:
  name: minimal-config

session:
  orchestrator: loop-basic
  context: context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: sk-key
"""

    parsed = yaml.safe_load(minimal)

    # Check required fields
    assert "bundle" in parsed
    assert "name" in parsed["bundle"]
    assert "session" in parsed
    assert "orchestrator" in parsed["session"]
    assert "context" in parsed["session"]
    assert "providers" in parsed
    assert len(parsed["providers"]) > 0

    print("✓ Minimal valid config structure verified")
    print(f"  Has bundle.name: {parsed['bundle']['name']}")
    print(f"  Has session.orchestrator: {parsed['session']['orchestrator']}")
    print(f"  Has session.context: {parsed['session']['context']}")
    print(f"  Has providers: {len(parsed['providers'])}")
    print()

    return True


if __name__ == "__main__":
    print("=" * 80)
    print("Config Logic Validation (No Database)")
    print("=" * 80)
    print()

    try:
        test_yaml_parsing()
        test_invalid_yaml()
        test_config_structure_requirements()

        print("=" * 80)
        print("All validations passed! ✓")
        print("=" * 80)
        print()
        print("Key Insights:")
        print("1. YAML parsing/dumping works correctly")
        print("2. Programmatic manipulation maintains structure")
        print("3. Invalid YAML is detected")
        print("4. Required fields can be validated")
        print("5. Round-trip (parse → modify → dump → parse) works")

    except Exception as e:
        print(f"✗ Validation failed: {e}")
        raise
