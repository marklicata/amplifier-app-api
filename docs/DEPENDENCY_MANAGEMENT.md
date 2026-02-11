# Dependency Management Strategy

## Overview

This service uses a **hybrid approach** to manage Amplifier dependencies, balancing stability with flexibility.

## Core Dependencies (Pre-installed)

### Amplifier Core Components
- **amplifier-core** @ main - The kernel
- **amplifier-foundation** @ main - Bundle system + built-in modules

### Pre-installed Provider Modules
- **amplifier-module-provider-anthropic** @ main
- **amplifier-module-provider-openai** @ main  
- **amplifier-module-provider-azure-openai** @ main

## What's Included in Foundation

Foundation bundle automatically includes:

### Orchestrators (Built-in)
- `loop-basic` - Simple request/response loop
- `loop-streaming` - Streaming responses with extended thinking

### Context Managers (Built-in)
- `context-simple` - Basic memory management
- `context-persistent` - Persistent conversation history

### Common Tools (Built-in)
- `tool-filesystem` - File operations
- `tool-bash` - Shell command execution
- `tool-web` - Web fetching
- Many more...

## User Config Best Practices

### ✅ DO: Reference by Name (Recommended)

```json
{
  "config_data": {
    "bundle": {"name": "my-config", "version": "1.0.0"}
  },
  "session": {
    "orchestrator": "loop-streaming",  // ← Just the name!
    "context": "context-simple"        // ← Just the name!
  },
  "providers": [
    {"module": "provider-anthropic"}   // ← Just the name!
  ]
}
```

**Benefits:**
- Uses pre-installed, version-compatible modules
- No runtime git cloning
- Faster session startup
- No version conflicts

### ❌ DON'T: Specify Sources for Pre-installed Modules

```json
// DON'T DO THIS:
"session": {
  "orchestrator": {
    "module": "loop-streaming",
    "source": "git+https://github.com/microsoft/amplifier-module-loop-streaming@main"  // ← Unnecessary!
  }
}

// DO THIS INSTEAD:
"session": {
  "orchestrator": "loop-streaming"  // ← Simple!
}
```

## Optional: Custom Modules

If you need modules NOT pre-installed:

```json
"tools": [
  {
    "module": "tool-custom",
    "source": "git+https://github.com/yourorg/custom-tool@main"
  }
]
```

These will be cloned at runtime when the session starts.

## Updating Pre-installed Modules

To update all pre-installed modules to latest:

1. Rebuild the Docker image: `docker-compose build`
2. Restart: `docker-compose up -d`

This pulls latest `@main` for all pre-installed components.

## Version Compatibility

**Current Strategy:** Pin all components to stable, tested versions (mid-January 2026 snapshot).

All bundled modules are tested together:
- amplifier-core @ 976fb87 (Jan 25, 2026)
- amplifier-foundation @ 412fcb5 (Feb 3, 2026)
- loop-streaming @ edcf55d (Jan 19, 2026)
- provider-anthropic @ 48299c2 (Jan 16, 2026)
- provider-openai @ fa7fca1 (Jan 15, 2026)
- provider-azure-openai @ 32aa9a4 (Jan 13, 2026)
- provider-gemini @ 1da7fd9 (Jan 14, 2026)
- provider-ollama @ 3858fc6 (Jan 3, 2026)
- provider-vllm @ c41a404 (Jan 12, 2026)

**Why pinned versions?**
- Stability: No breaking changes from upstream @main branches
- Predictability: Same behavior across deployments
- Compatibility: All versions tested together

**If you experience version issues:**
1. Check if you're specifying `source` URLs in configs (remove them - use names only)
2. Use foundation's built-in modules (always compatible with pinned core)

## Migration Guide

### Old Config (with sources)
```json
{
  "session": {
    "orchestrator": {
      "module": "loop-streaming",
      "source": "git+https://..."
    }
  },
  "providers": [
    {
      "module": "provider-anthropic",
      "source": "git+https://..."
    }
  ]
}
```

### New Config (reference by name)
```json
{
  "session": {
    "orchestrator": "loop-streaming"
  },
  "providers": [
    {"module": "provider-anthropic"}
  ]
}
```

**Changes:**
- Remove `source` fields for pre-installed modules
- Simplify to just module name/identifier

## Summary

| Component | Pre-installed? | Reference Method |
|-----------|----------------|------------------|
| Orchestrators (loop-basic, loop-streaming) | ✅ Yes (via foundation) | Name only: `"loop-basic"` |
| Context managers (context-simple, etc.) | ✅ Yes (via foundation) | Name only: `"context-simple"` |
| Common tools (filesystem, bash, web) | ✅ Yes (via foundation) | Name only: `"tool-bash"` |
| Provider: Anthropic | ✅ Yes | Name only: `{"module": "provider-anthropic"}` |
| Provider: OpenAI | ✅ Yes | Name only: `{"module": "provider-openai"}` |
| Provider: Azure OpenAI | ✅ Yes | Name only: `{"module": "provider-azure-openai"}` |
| Provider: Gemini | ✅ Yes | Name only: `{"module": "provider-gemini"}` |
| Provider: Ollama | ✅ Yes | Name only: `{"module": "provider-ollama"}` |
| Provider: vLLM | ✅ Yes | Name only: `{"module": "provider-vllm"}` |
| Custom modules | ❌ No | With source: `{"module": "...", "source": "git+..."}` |
