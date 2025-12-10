"""Agent Delegation Example - Multi-agent workflows with session spawning.

This example demonstrates how to use the session spawner for delegating
tasks to specialized agents.

Total Lines: ~60 LOC

Usage:
    uv run python examples/agent_delegation.py
"""

import asyncio

from amplifier_core import AmplifierSession
from amplifier_app_utils import (
    PathManager,
    SessionStore,
    resolve_app_config,
    spawn_sub_session,
)


async def main():
    """Run an agent delegation example."""
    # Set up configuration
    pm = PathManager(app_name="agent-delegation-example")
    config_mgr = pm.create_config_manager()
    profile_loader = pm.create_profile_loader()
    agent_loader = pm.create_agent_loader()

    # Resolve config
    config = resolve_app_config(
        config_manager=config_mgr,
        profile_loader=profile_loader,
        agent_loader=agent_loader,
    )

    # Create parent session
    parent_session = AmplifierSession(config=config)
    await parent_session.initialize()

    print("🤖 Agent Delegation Example")
    print()

    # Get agent configs from profile/settings
    agent_configs = config.get("agents", {})

    if not agent_configs:
        print("⚠️  No agents configured. Add agents to your profile or settings.")
        print(f"📍 Config location: {pm.user_config_dir}")
        await parent_session.cleanup()
        return

    print(f"📋 Available agents: {', '.join(agent_configs.keys())}")
    print()

    # Example 1: Delegate a task to an agent
    agent_name = list(agent_configs.keys())[0]  # Use first agent
    print(f"🎯 Delegating task to '{agent_name}'...")

    result = await spawn_sub_session(
        agent_name=agent_name,
        instruction="Explain what you do in one sentence.",
        parent_session=parent_session,
        agent_configs=agent_configs,
        session_store=SessionStore(),
    )

    print(f"✅ {agent_name}: {result['output']}")
    print(f"📝 Session ID: {result['session_id']}")
    print()

    # Example 2: Multi-turn conversation (resume session)
    print(f"🔄 Continuing conversation with '{agent_name}'...")
    from amplifier_app_utils import resume_sub_session

    result2 = await resume_sub_session(
        sub_session_id=result["session_id"],
        instruction="Can you elaborate on that?",
        session_store=SessionStore(),
    )

    print(f"✅ {agent_name}: {result2['output']}")
    print()

    # Cleanup
    await parent_session.cleanup()
    print("👋 Done!")


if __name__ == "__main__":
    asyncio.run(main())
