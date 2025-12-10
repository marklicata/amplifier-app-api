# Quick Start - Amplifier Foundation

## Installation

```bash
# Once published to PyPI:
pip install amplifier-foundation

# For now (development):
cd amplifier-foundation
pip install -e .
```

## Minimal Example (25 lines)

```python
"""A complete Amplifier application in 25 lines."""

import asyncio
from amplifier_core import AmplifierSession
from amplifier_app_utils import PathManager, resolve_app_config


async def main():
    # Set up paths (5 lines)
    pm = PathManager(app_name="my-app")
    config_mgr = pm.create_config_manager()
    profile_loader = pm.create_profile_loader()
    agent_loader = pm.create_agent_loader()

    # Resolve configuration (6 lines)
    config = resolve_app_config(
        config_manager=config_mgr,
        profile_loader=profile_loader,
        agent_loader=agent_loader,
    )

    # Create session (3 lines)
    session = AmplifierSession(config=config)
    await session.initialize()

    # Use it! (2 lines)
    response = await session.execute("Hello, world!")
    print(response)

    # Cleanup (2 lines)
    await session.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
```

## What You Get

### Path Management ✅
```python
from amplifier_app_utils import PathManager

pm = PathManager(app_name="my-app")
print(pm.user_config_dir)    # ~/.config/my-app (Linux/Mac)
print(pm.workspace_dir)       # ~/amplifier_workspace
print(pm.keys_file)           # ~/.amplifier/keys.env
```

### Provider Management ✅
```python
from amplifier_app_utils import ProviderManager

mgr = ProviderManager(config_manager)
mgr.use_provider(
    provider_id="provider-anthropic",
    scope="global",
    config={"model": "claude-3-5-sonnet-20241022"}
)
```

### Session Persistence ✅
```python
from amplifier_app_utils import SessionStore

store = SessionStore()
store.save("my-session", messages, metadata)
messages, metadata = store.load("my-session")
```

### Agent Delegation ✅
```python
from amplifier_app_utils import spawn_sub_session

result = await spawn_sub_session(
    agent_name="researcher",
    instruction="Research topic X",
    parent_session=session,
    agent_configs=config["agents"],
    session_store=SessionStore(),
)

print(result["output"])
print(result["session_id"])  # For multi-turn
```

### Key Management ✅
```python
from amplifier_app_utils import KeyManager

keys = KeyManager()
keys.save_key("anthropic", "sk-ant-...")
print(keys.has_key("anthropic"))  # True
```

### Configuration Resolution ✅
```python
from amplifier_app_utils import resolve_app_config

config = resolve_app_config(
    config_manager=config_mgr,
    profile_loader=profile_loader,
    agent_loader=agent_loader,
    provider_overrides={"provider-anthropic": {...}},
    cli_config={"tools": [...]},
)
# Automatically handles:
# - Profile loading
# - Settings merging (user → project → local)
# - Provider overrides
# - CLI overrides
# - Environment variable expansion
```

## More Examples

See the `examples/` directory:

- **minimal_repl.py** - Simplest Amplifier app (25 LOC)
- **agent_delegation.py** - Multi-agent workflows (60 LOC)
- **custom_provider.py** - Provider configuration (50 LOC)

## Common Patterns

### REPL Application

```python
async def repl():
    pm = PathManager(app_name="my-repl")
    # ... setup ...
    session = AmplifierSession(config=config)
    await session.initialize()
    
    while True:
        user_input = input("You: ")
        if user_input == "exit":
            break
        response = await session.execute(user_input)
        print(f"AI: {response}")
    
    await session.cleanup()
```

### API Server

```python
from fastapi import FastAPI
from amplifier_app_utils import PathManager, resolve_app_config

app = FastAPI()
pm = PathManager(app_name="my-api")
# ... setup config ...

@app.post("/chat")
async def chat(message: str):
    session = AmplifierSession(config=config)
    await session.initialize()
    response = await session.execute(message)
    await session.cleanup()
    return {"response": response}
```

### Desktop GUI

```python
from PyQt6.QtWidgets import QApplication, QMainWindow
from amplifier_app_utils import PathManager, resolve_app_config

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.pm = PathManager(app_name="my-gui")
        # ... setup config ...
        self.session = None
    
    async def initialize_session(self):
        self.session = AmplifierSession(config=config)
        await self.session.initialize()
    
    async def send_message(self, text):
        return await self.session.execute(text)
```

## Configuration Files

### Keys (~/.amplifier/keys.env)

```bash
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

### Settings (~/.config/my-app/user.yaml)

```yaml
modules:
  tools:
    - module: tool-shell
    - module: tool-file-editor

profiles:
  default: dev-profile
```

### Profiles (~/.config/my-app/profiles/custom.yaml)

```yaml
name: custom
description: My custom profile

providers:
  - module: provider-anthropic
    config:
      model: claude-3-5-sonnet-20241022

tools:
  - module: tool-shell
  - module: tool-file-editor

agents:
  researcher:
    name: Researcher
    system:
      instruction: You are a research assistant...
```

## API Reference

See the main README.md for complete API documentation.

### Core Classes

- **PathManager** - Path and configuration management
- **ProviderManager** - Provider lifecycle
- **ModuleManager** - Module configuration
- **SessionStore** - Session persistence
- **KeyManager** - API key storage
- **AppSettings** - High-level settings helpers

### Functions

- **resolve_app_config()** - Config assembly
- **spawn_sub_session()** - Agent delegation
- **resume_sub_session()** - Multi-turn agents
- **get_effective_provider_sources()** - Provider sources
- **get_project_slug()** - Project identification

## Troubleshooting

### No Provider Configured

```bash
$ amplifier provider use anthropic
$ echo "ANTHROPIC_API_KEY=sk-..." >> ~/.amplifier/keys.env
```

### Module Not Found

```bash
$ amplifier module add tool-shell --scope global
```

### Profile Not Found

```bash
$ amplifier profile activate my-profile
```

## Next Steps

1. **Read the examples** - `examples/` directory
2. **Check the API docs** - Main README.md
3. **Build your app** - Start with minimal_repl.py
4. **Join the community** - GitHub Discussions

## Support

- **Documentation:** README.md
- **Examples:** examples/
- **Issues:** GitHub Issues
- **Discussions:** GitHub Discussions

---

**Ready to build?** Start with `examples/minimal_repl.py`! 🚀
