"""Custom Provider Example - Configure and use providers.

This example shows how to configure providers, manage API keys,
and switch between different providers.

Total Lines: ~50 LOC

Usage:
    uv run python examples/custom_provider.py
"""

import asyncio

from amplifier_core import AmplifierSession
from amplifier_app_utils import (
    KeyManager,
    PathManager,
    ProviderManager,
    resolve_app_config,
)


async def main():
    """Run a custom provider example."""
    # Set up
    pm = PathManager(app_name="custom-provider-example")
    config_mgr = pm.create_config_manager()
    profile_loader = pm.create_profile_loader()
    agent_loader = pm.create_agent_loader()

    print("🔧 Custom Provider Configuration Example")
    print()

    # Example 1: Check for API keys
    key_mgr = KeyManager()
    print("🔑 Checking API keys...")

    if key_mgr.has_key("anthropic"):
        print("  ✅ Anthropic API key found")
    else:
        print("  ⚠️  Anthropic API key not found")
        print(f"     Set it in: {pm.keys_file}")

    if key_mgr.has_key("openai"):
        print("  ✅ OpenAI API key found")
    else:
        print("  ⚠️  OpenAI API key not found")

    print()

    # Example 2: Configure a provider
    provider_mgr = ProviderManager(config_mgr)
    print("⚙️  Configuring Anthropic provider...")

    result = provider_mgr.use_provider(
        provider_id="provider-anthropic",
        scope="global",
        config={
            "model": "claude-3-5-sonnet-20241022",
            "temperature": 0.7,
        },
    )

    print(f"  ✅ {result.message}")
    print(f"     Scope: {result.scope}")
    print()

    # Example 3: Use the configured provider
    config = resolve_app_config(
        config_manager=config_mgr,
        profile_loader=profile_loader,
        agent_loader=agent_loader,
    )

    session = AmplifierSession(config=config)
    await session.initialize()

    print("💬 Testing provider...")
    response = await session.execute("Say hello in one sentence.")
    print(f"  AI: {response}")
    print()

    # Example 4: List current providers
    print("📋 Current providers:")
    for provider in provider_mgr.list_providers():
        print(f"  - {provider.module} ({provider.scope})")
        if provider.config:
            print(f"    Model: {provider.config.get('model', 'default')}")

    # Cleanup
    await session.cleanup()
    print("\n👋 Done!")


if __name__ == "__main__":
    asyncio.run(main())
