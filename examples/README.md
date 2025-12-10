# Amplifier Foundation Examples

This directory contains example applications demonstrating how to use the Amplifier Foundation library.

## Examples

### 1. Minimal REPL (`minimal_repl.py`)

The simplest possible Amplifier application. Demonstrates the absolute minimum code needed to create a working AI application.

**Lines of Code:** ~25  
**Key Concepts:**
- PathManager setup
- Configuration resolution
- Session creation
- Basic REPL loop

### 2. API Server (`api_server.py`)

A FastAPI-based REST API for Amplifier. Shows how to build a stateless API service.

**Lines of Code:** ~80  
**Key Concepts:**
- Stateless session management
- Request/response handling
- Configuration injection
- Error handling

### 3. Agent Delegation (`agent_delegation.py`)

Demonstrates using the session spawner for multi-agent workflows.

**Lines of Code:** ~60  
**Key Concepts:**
- Sub-session creation
- Agent configuration
- Multi-turn conversations
- Session persistence

### 4. Custom Provider (`custom_provider.py`)

Shows how to configure and use providers with the foundation.

**Lines of Code:** ~40  
**Key Concepts:**
- Provider configuration
- Key management
- Source resolution
- Provider switching

## Running Examples

### Prerequisites

```bash
# Install the foundation library
cd amplifier-foundation
uv pip install -e .

# Or install from PyPI (once published)
uv pip install amplifier-foundation
```

### Run an Example

```bash
# Minimal REPL
uv run python examples/minimal_repl.py

# API Server
uv run python examples/api_server.py

# Agent Delegation
uv run python examples/agent_delegation.py

# Custom Provider
uv run python examples/custom_provider.py
```

## Key Takeaways

### Before Amplifier Foundation

Building an Amplifier app required 500+ lines of boilerplate:
- Manually configure 5 dependencies
- Replicate path logic across apps
- Handle provider discovery manually
- Implement session persistence from scratch
- Duplicate configuration resolution logic

### After Amplifier Foundation

Building an Amplifier app requires ~25 lines:
```python
from amplifier_app_utils import PathManager, resolve_app_config
from amplifier_core import AmplifierSession

pm = PathManager(app_name="my-app")
config_mgr = pm.create_config_manager()
profile_loader = pm.create_profile_loader()
agent_loader = pm.create_agent_loader()

config = resolve_app_config(
    config_manager=config_mgr,
    profile_loader=profile_loader,
    agent_loader=agent_loader,
)

session = AmplifierSession(config=config)
await session.initialize()

# Your app logic here
```

**That's a 95% reduction in boilerplate!** 🚀

## Architecture Benefits

1. **Single Dependency** - Just `amplifier-foundation` instead of 5 packages
2. **Zero Boilerplate** - Path management, config resolution, providers all handled
3. **Type Safe** - Full type hints for IDE support
4. **Well Tested** - 111 tests ensure reliability
5. **Flexible** - Easy to customize for any use case

## Next Steps

1. **Explore the examples** - Learn by example
2. **Read the API docs** - Understand the full capabilities
3. **Build your app** - Start with minimal_repl.py and extend
4. **Contribute** - Share your examples and improvements

## Support

- **Documentation:** See main README.md
- **Issues:** Report on GitHub
- **Discussions:** Join the community
- **Examples:** This directory

---

**Happy building!** 🎉
