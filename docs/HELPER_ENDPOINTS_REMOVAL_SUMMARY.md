# Helper Endpoints Removal Summary

This document summarizes the removal of the config helper endpoints (`/configs/{id}/tools`, `/configs/{id}/providers`, `/configs/{id}/bundles`).

## What Was Removed

### Removed Endpoints (3 total)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/configs/{config_id}/tools` | POST | ~~Add tool to config YAML~~ |
| `/configs/{config_id}/providers` | POST | ~~Add provider to config YAML~~ |
| `/configs/{config_id}/bundles` | POST | ~~Add bundle to config YAML~~ |

### Reason for Removal

These endpoints added unnecessary complexity. Users can achieve the same result more directly by:

1. **GET** the config to retrieve current YAML
2. **Modify** the YAML content as needed
3. **PUT** the updated YAML back

This approach is:
- ✅ **Simpler** - Fewer endpoints to learn and maintain
- ✅ **More Flexible** - Users can make any YAML modifications
- ✅ **Standard REST** - Uses standard CRUD operations

## Files Changed

### Modified Files

1. **`amplifier_app_api/api/config.py`**
   - Removed 3 helper endpoint functions
   - Reduced from ~365 lines to ~227 lines

2. **`amplifier_app_api/core/config_manager.py`**
   - Removed `add_tool_to_config()` method
   - Removed `add_provider_to_config()` method
   - Removed `merge_bundle_into_config()` method

3. **`tests/test_configs_crud.py`**
   - Removed `TestConfigHelperEndpoints` class (7 test methods)
   - Reduced test count from 40+ to 33

4. **`docs/CONFIG_API.md`**
   - Removed "Helper Endpoints" section
   - Updated examples to use PUT for modifications

5. **`docs/CONFIG_ENDPOINTS_SUMMARY.md`**
   - Removed helper endpoint examples
   - Updated endpoint count (8 → 5)

6. **`README.md`**
   - Updated Configuration section (8 → 5 endpoints)
   - Updated total endpoint count (40 → 37)

## Migration Guide

### Before (Using Helper Endpoints)

```bash
# Old way - using helper endpoints
curl -X POST "http://localhost:8765/configs/$CONFIG_ID/tools" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_module": "tool-web",
    "tool_source": "git+https://github.com/example/tool-web"
  }'

curl -X POST "http://localhost:8765/configs/$CONFIG_ID/providers" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_module": "provider-anthropic",
    "provider_config": {"default_model": "claude-sonnet-4-5"}
  }'

curl -X POST "http://localhost:8765/configs/$CONFIG_ID/bundles" \
  -H "Content-Type: application/json" \
  -d '{
    "bundle_uri": "git+https://github.com/microsoft/amplifier-foundation@main"
  }'
```

### After (Using PUT)

```bash
# New way - get, modify, put
# 1. Get current config
CURRENT_YAML=$(curl -s "http://localhost:8765/configs/$CONFIG_ID" | jq -r '.yaml_content')

# 2. Create updated YAML (you can do this programmatically)
NEW_YAML="bundle:
  name: my-bundle
  version: 1.0.0

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main

providers:
  - module: provider-anthropic
    config:
      default_model: claude-sonnet-4-5-20250929

tools:
  - module: tool-web
    source: git+https://github.com/example/tool-web
"

# 3. Update config
curl -X PUT "http://localhost:8765/configs/$CONFIG_ID" \
  -H "Content-Type: application/json" \
  -d "{\"yaml_content\": $(echo "$NEW_YAML" | jq -Rs .)}"
```

### Programmatic Updates (Python Example)

```python
import requests
import yaml

# Get current config
response = requests.get(f"http://localhost:8765/configs/{config_id}")
config = response.json()

# Parse YAML
config_dict = yaml.safe_load(config["yaml_content"])

# Add a tool
if "tools" not in config_dict:
    config_dict["tools"] = []

config_dict["tools"].append({
    "module": "tool-web",
    "source": "git+https://github.com/example/tool-web"
})

# Add a provider
if "providers" not in config_dict:
    config_dict["providers"] = []

config_dict["providers"].append({
    "module": "provider-anthropic",
    "config": {
        "default_model": "claude-sonnet-4-5-20250929"
    }
})

# Add a bundle
if "includes" not in config_dict:
    config_dict["includes"] = []

config_dict["includes"].append({
    "bundle": "git+https://github.com/microsoft/amplifier-foundation@main"
})

# Convert back to YAML
updated_yaml = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)

# Update config
requests.put(
    f"http://localhost:8765/configs/{config_id}",
    json={"yaml_content": updated_yaml}
)
```

### JavaScript Example

```javascript
// Fetch current config
const response = await fetch(`http://localhost:8765/configs/${configId}`);
const config = await response.json();

// Parse YAML (using js-yaml library)
const jsyaml = require('js-yaml');
const configDict = jsyaml.load(config.yaml_content);

// Add tool
if (!configDict.tools) configDict.tools = [];
configDict.tools.push({
  module: 'tool-web',
  source: 'git+https://github.com/example/tool-web'
});

// Add provider
if (!configDict.providers) configDict.providers = [];
configDict.providers.push({
  module: 'provider-anthropic',
  config: {
    default_model: 'claude-sonnet-4-5-20250929'
  }
});

// Add bundle
if (!configDict.includes) configDict.includes = [];
configDict.includes.push({
  bundle: 'git+https://github.com/microsoft/amplifier-foundation@main'
});

// Convert back to YAML
const updatedYaml = jsyaml.dump(configDict);

// Update config
await fetch(`http://localhost:8765/configs/${configId}`, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ yaml_content: updatedYaml })
});
```

## Benefits of This Change

### ✅ Simpler API Surface
- **Before:** 8 config endpoints (5 CRUD + 3 helpers)
- **After:** 5 config endpoints (5 CRUD only)
- **Reduction:** 37.5% fewer endpoints to learn and maintain

### ✅ More Flexibility
- Helper endpoints could only add items (append to arrays)
- PUT allows any modifications: add, remove, reorder, change existing items

### ✅ Standard REST Patterns
- Uses standard PUT for updates
- No custom helper endpoints
- Follows REST best practices

### ✅ Less Code to Maintain
- Removed ~200 lines of endpoint code
- Removed 7 test methods
- Removed ~150 lines of documentation

## Updated API Summary

### Config Endpoints (5)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/configs` | Create config |
| GET | `/configs` | List configs |
| GET | `/configs/{id}` | Get config |
| PUT | `/configs/{id}` | Update config (modify YAML) |
| DELETE | `/configs/{id}` | Delete config |

### Global Registries (Still Available!)

The global registries for tools, providers, and bundles are **still available** and unchanged:

| Registry | Endpoints | Purpose |
|----------|-----------|---------|
| **Tools** | POST/GET/DELETE `/tools` | Register and discover tools |
| **Providers** | POST/GET/DELETE `/providers` | Register and discover providers |
| **Bundles** | POST/GET/DELETE `/bundles` | Register and discover bundles |

## FAQs

### Q: Can I still add tools/providers/bundles to configs?

**A:** Yes! Just use `PUT /configs/{id}` with updated YAML content. See the migration guide above.

### Q: Are the global registries affected?

**A:** No! The tool, provider, and bundle registries are unchanged. You can still:
- Register components globally
- List available components
- Use them when building configs

### Q: What if I was using the helper endpoints?

**A:** Update your code to use `PUT /configs/{id}` instead. See the migration examples above for Python and JavaScript.

### Q: Is this a breaking change?

**A:** Yes, the helper endpoints are removed. If you were using them, you'll need to update your code to use PUT for config modifications.

## Timeline

- **Implemented:** 2026-02-06
- **Status:** Complete
- **Version:** API v2 (with registries, without helper endpoints)

## Summary

✅ **Removed:** 3 config helper endpoints
✅ **Simplified:** API surface reduced by 3 endpoints (40 → 37 total)
✅ **Migration:** Use PUT /configs/{id} for YAML modifications
✅ **Registries:** Global tool, provider, and bundle registries unchanged

The API is now simpler and follows standard REST patterns while maintaining all functionality through the UPDATE endpoint.
