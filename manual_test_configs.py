"""Manual test script to demonstrate the new Config → Session architecture."""

import asyncio
from pathlib import Path

from amplifier_app_api.core.config_manager import ConfigManager
from amplifier_app_api.storage import Database


async def main():
    """Demonstrate the new architecture."""
    print("=" * 80)
    print("Config → Session Architecture Demo")
    print("=" * 80)
    print()

    # Setup database
    db_path = Path("./test_demo.db")
    if db_path.exists():
        db_path.unlink()

    db = Database(db_path)
    await db.connect()

    manager = ConfigManager(db)

    # 1. Create a config
    print("1. Creating a config with complete YAML bundle...")
    yaml_content = """
bundle:
  name: demo-config
  version: 1.0.0
  description: Demo configuration

includes:
  - bundle: foundation

providers:
  - module: provider-anthropic
    config:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-5
      max_tokens: 4096

session:
  orchestrator: loop-streaming
  context: context-persistent

tools:
  - module: tool-filesystem
    config:
      allowed_paths: ["."]
  
  - module: tool-bash
    config:
      timeout_seconds: 30
  
  - module: tool-web

hooks:
  - module: hooks-logging
    config:
      output_dir: .amplifier/logs
"""

    config = await manager.create_config(
        name="demo-config",
        yaml_content=yaml_content,
        description="Demo configuration for testing",
        tags={"env": "demo", "version": "1.0"},
    )

    print(f"✓ Created config: {config.config_id}")
    print(f"  Name: {config.name}")
    print(f"  Description: {config.description}")
    print(f"  Tags: {config.tags}")
    print()

    # 2. Retrieve the config
    print("2. Retrieving the config...")
    retrieved = await manager.get_config(config.config_id)
    assert retrieved is not None
    print(f"✓ Retrieved config: {retrieved.name}")
    print()

    # 3. Parse the YAML
    print("3. Parsing YAML content...")
    parsed = manager.parse_yaml(retrieved.yaml_content)
    print(f"✓ Bundle name: {parsed['bundle']['name']}")
    print(f"✓ Includes: {len(parsed.get('includes', []))} bundles")
    print(f"✓ Providers: {len(parsed.get('providers', []))} configured")
    print(f"✓ Tools: {len(parsed.get('tools', []))} configured")
    print()

    # 4. Add a tool programmatically
    print("4. Adding a tool programmatically...")
    updated = await manager.add_tool_to_config(
        config.config_id,
        module="tool-search",
        source="git+https://github.com/microsoft/amplifier-module-tool-search@main",
        config={"provider": "brave", "max_results": 10},
    )
    assert updated is not None
    parsed = manager.parse_yaml(updated.yaml_content)
    print(f"✓ Tools after addition: {len(parsed['tools'])}")
    print()

    # 5. Add a provider programmatically
    print("5. Adding another provider...")
    updated = await manager.add_provider_to_config(
        config.config_id,
        module="provider-openai",
        config={"api_key": "${OPENAI_API_KEY}", "model": "gpt-4o"},
    )
    assert updated is not None
    parsed = manager.parse_yaml(updated.yaml_content)
    print(f"✓ Providers after addition: {len(parsed['providers'])}")
    print()

    # 6. Merge a bundle
    print("6. Merging another bundle...")
    updated = await manager.merge_bundle_into_config(
        config.config_id,
        bundle_uri="git+https://github.com/microsoft/amplifier-bundle-recipes@main",
    )
    assert updated is not None
    parsed = manager.parse_yaml(updated.yaml_content)
    print(f"✓ Includes after merge: {len(parsed['includes'])}")
    print()

    # 7. Update metadata
    print("7. Updating config metadata...")
    updated = await manager.update_config(
        config.config_id,
        description="Updated demo configuration",
        tags={"env": "demo", "version": "1.1", "tested": "true"},
    )
    assert updated is not None
    print(f"✓ Updated description: {updated.description}")
    print(f"✓ Updated tags: {updated.tags}")
    print()

    # 8. Create multiple configs
    print("8. Creating additional configs...")
    config2 = await manager.create_config(
        name="production-config",
        yaml_content="bundle:\n  name: prod\nincludes:\n  - bundle: foundation",
    )
    config3 = await manager.create_config(
        name="staging-config",
        yaml_content="bundle:\n  name: staging\nincludes:\n  - bundle: foundation",
    )
    print(f"✓ Created config 2: {config2.name}")
    print(f"✓ Created config 3: {config3.name}")
    print()

    # 9. List all configs
    print("9. Listing all configs...")
    configs, total = await manager.list_configs(limit=10, offset=0)
    print(f"✓ Total configs: {total}")
    for cfg in configs:
        print(f"  - {cfg.name} ({cfg.config_id})")
    print()

    # 10. Test pagination
    print("10. Testing pagination...")
    page1, total = await manager.list_configs(limit=2, offset=0)
    page2, _ = await manager.list_configs(limit=2, offset=2)
    print(f"✓ Page 1: {len(page1)} configs")
    print(f"✓ Page 2: {len(page2)} configs")
    print()

    # 11. Show final YAML
    print("11. Final YAML content of demo-config:")
    print("-" * 80)
    final_config = await manager.get_config(config.config_id)
    assert final_config is not None
    print(final_config.yaml_content)
    print("-" * 80)
    print()

    # Cleanup
    print("Cleaning up...")
    await manager.delete_config(config.config_id)
    await manager.delete_config(config2.config_id)
    await manager.delete_config(config3.config_id)
    print("✓ Deleted all demo configs")
    print()

    await db.disconnect()
    db_path.unlink()

    print("=" * 80)
    print("Demo complete!")
    print("=" * 80)
    print()
    print("Key Takeaways:")
    print("1. Configs store complete YAML bundles")
    print("2. Configs can be manipulated programmatically via helpers")
    print("3. Sessions will reference configs via config_id")
    print("4. Multiple sessions can share the same config")
    print("5. YAML validation happens on create/update")


if __name__ == "__main__":
    asyncio.run(main())
