"""Minimal REPL - The simplest possible Amplifier application.

This example demonstrates the absolute minimum code needed to create
a working AI application using Amplifier Foundation.

Total Lines: ~25 LOC

Usage:
    uv run python examples/minimal_repl.py
"""

import asyncio

from amplifier_core import AmplifierSession
from amplifier_app_utils import PathManager, resolve_app_config


async def main():
    """Run a minimal REPL."""
    # Set up paths and configuration
    pm = PathManager(app_name="minimal-repl")
    config_mgr = pm.create_config_manager()
    profile_loader = pm.create_profile_loader()
    agent_loader = pm.create_agent_loader()

    # Resolve configuration (handles profiles, settings, env vars)
    config = resolve_app_config(
        config_manager=config_mgr,
        profile_loader=profile_loader,
        agent_loader=agent_loader,
    )

    # Create and initialize session
    session = AmplifierSession(config=config)
    await session.initialize()

    print("🚀 Minimal REPL ready! (Type 'exit' to quit)")
    print(f"📍 Config: {pm.user_config_dir}")
    print()

    # Simple REPL loop
    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in ("exit", "quit", "q"):
                break
            if not user_input:
                continue

            # Execute and print response
            response = await session.execute(user_input)
            print(f"AI: {response}\n")

        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"Error: {e}\n")

    # Cleanup
    await session.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
