# Manual Testing Guide - Config & Session Architecture

This guide walks you through manually testing the new Config → Session architecture.

---

## Prerequisites

### 1. Install Dependencies
```bash
# Ensure uv is installed
which uv

# Install project dependencies
uv sync
```

### 2. Verify Database Schema
```bash
# The database will be auto-created on first run at:
# data/amplifier.db (or path in .env)

# To start fresh:
rm -f data/amplifier.db
```

### 3. Check Environment
```bash
# Copy example env
cp .env.example .env

# Edit .env and set paths (if needed):
# AMPLIFIER_CORE_PATH=/path/to/amplifier-core
# AMPLIFIER_FOUNDATION_PATH=/path/to/amplifier-foundation
```

---

## Step 1: Start the Service

### Option A: Direct Run
```bash
uv run uvicorn amplifier_app_api.main:app --reload --host 0.0.0.0 --port 8000
```

### Option B: Using run-dev.sh
```bash
./run-dev.sh
```

**Expected Output:**
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Verify:**
```bash
curl http://localhost:8765/health
```

Should return:
```json
{
  "status": "healthy",
  "version": "0.3.0",
  "database_connected": true,
  "uptime_seconds": 1.23
}
```

---

## Step 2: Test Config Creation

### 2.1 Create a Minimal Config

```bash
curl -X POST http://localhost:8765/configs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test-minimal",
    "description": "Minimal test config",
    "yaml_content": "bundle:\n  name: test-minimal\n  version: 1.0.0\n\nincludes:\n  - bundle: foundation\n\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: sk-test-key\n      model: claude-sonnet-4-5\n\nsession:\n  orchestrator: loop-basic\n  context: context-simple"
  }'
```

**Expected Response:**
```json
{
  "config_id": "c7a3f9e2-1b4d-4c8a-9f2e-d6b8a1c5e3f7",
  "name": "test-minimal",
  "description": "Minimal test config",
  "yaml_content": "bundle:\n  name: test-minimal\n...",
  "created_at": "2026-02-04T16:00:00Z",
  "updated_at": "2026-02-04T16:00:00Z",
  "tags": {},
  "message": "Config created successfully"
}
```

**Save the config_id for later steps!**

---

### 2.2 Create a Full Config with Markdown

Create a file `test-config.yaml`:

```yaml
---
bundle:
  name: full-test-config
  version: 1.0.0
  description: Full test configuration

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

context:
  config:
    max_tokens: 200000
    compact_threshold: 0.92

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

---

# Test Assistant

You are a helpful test assistant with access to filesystem, bash, and web tools.

## Guidelines

- Be helpful and precise
- Use tools when appropriate
```

Then create via API:

```bash
curl -X POST http://localhost:8765/configs \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{
  "name": "full-test-config",
  "description": "Full configuration with markdown body",
  "yaml_content": $(cat test-config.yaml | jq -Rs .),
  "tags": {
    "env": "test",
    "type": "full"
  }
}
EOF
```

**Expected:** Returns config with config_id

---

## Step 3: Test Config Retrieval

### 3.1 Get Specific Config
```bash
curl http://localhost:8765/configs/{config_id}
```

Replace `{config_id}` with the ID from step 2.1.

**Expected:** Full config with YAML content

---

### 3.2 List All Configs
```bash
curl http://localhost:8765/configs?limit=10&offset=0
```

**Expected Response:**
```json
{
  "configs": [
    {
      "config_id": "...",
      "name": "test-minimal",
      "description": "Minimal test config",
      "created_at": "...",
      "updated_at": "...",
      "tags": {}
    },
    {
      "config_id": "...",
      "name": "full-test-config",
      "description": "Full configuration with markdown body",
      "created_at": "...",
      "updated_at": "...",
      "tags": {"env": "test", "type": "full"}
    }
  ],
  "total": 2
}
```

**Verify:**
- Both configs appear in list
- Metadata is correct (no yaml_content in list)
- Tags are present

---

## Step 4: Test Config Updates

### 4.1 Update Config Name
```bash
curl -X PUT http://localhost:8765/configs/{config_id} \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test-minimal-updated"
  }'
```

**Expected:** Returns updated config with new name, unchanged YAML

---

### 4.2 Update YAML Content
```bash
curl -X PUT http://localhost:8765/configs/{config_id} \
  -H "Content-Type: application/json" \
  -d '{
    "yaml_content": "bundle:\n  name: test-minimal\n  version: 1.0.1\n\nincludes:\n  - bundle: foundation\n\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: sk-test-key\n      model: claude-sonnet-4-5\n\nsession:\n  orchestrator: loop-streaming\n  context: context-simple"
  }'
```

**Expected:** Returns config with updated YAML (version changed to 1.0.1, orchestrator changed)

---

### 4.3 Test Invalid YAML Rejection
```bash
curl -X PUT http://localhost:8765/configs/{config_id} \
  -H "Content-Type: application/json" \
  -d '{
    "yaml_content": "bundle\n  name test"
  }'
```

**Expected:** HTTP 400 with error message about invalid YAML

---

## Step 5: Update Config with Additional Components

To add more tools, providers, or modules to a config, update the config_data via PUT:

### 5.1 Get Current Config
```bash
CONFIG_ID="your-config-id-from-step-2"
curl http://localhost:8765/configs/$CONFIG_ID | jq -r '.config_data' > current.json
```

### 5.2 Modify the YAML

Edit `current.yaml` to add components:

```yaml
bundle:
  name: test-minimal
  version: 2.0.0

includes:
  - bundle: foundation
  - bundle: recipes  # Added

session:
  orchestrator: loop-streaming  # Changed from loop-basic
  context: context-persistent    # Changed from context-simple

providers:
  - module: provider-anthropic
    config:
      api_key: sk-test-key
      model: claude-sonnet-4-5
  - module: provider-openai  # Added
    config:
      api_key: ${OPENAI_API_KEY}
      model: gpt-4o

tools:  # Added section
  - module: tool-filesystem
  - module: tool-bash
  - module: tool-search
    config:
      timeout_seconds: 30
```

### 5.3 Update Config

```bash
# Read modified YAML and update
UPDATED_YAML=$(cat current.yaml)

curl -X PUT "http://localhost:8765/configs/$CONFIG_ID" \
  -H "Content-Type: application/json" \
  -d "{\"yaml_content\": $(echo "$UPDATED_YAML" | jq -Rs .)}"
```

**Expected:** `200 OK` with updated configuration

**Verify:**
```bash
curl http://localhost:8765/configs/$CONFIG_ID | jq -r '.yaml_content'
# Should show all your changes
```

---

## Step 6: Test Session Creation (Integration Test)

**⚠️ Note:** This step requires amplifier-core and amplifier-foundation to be available at the paths specified in your `.env` file.

### 6.1 Create Session from Config

```bash
curl -X POST http://localhost:8765/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "config_id": "{config_id}"
  }'
```

Replace `{config_id}` with an actual config ID.

**Expected Response (Success):**
```json
{
  "session_id": "s1a2b3c4-5d6e-7f8g-9h0i-1j2k3l4m5n6o",
  "config_id": "c7a3f9e2-1b4d-4c8a-9f2e-d6b8a1c5e3f7",
  "status": "active",
  "message": "Session created successfully"
}
```

**What This Tests:**
- Config → YAML string → dict conversion
- `Bundle.from_dict()` works correctly
- Bundle preparation succeeds
- AmplifierSession creation works
- Session stored in database

**Expected Logs (in console):**
```
INFO: Parsed YAML for config: {config_id}
INFO: Created Bundle from config dict: {config_id}
INFO: Preparing bundle for config: {config_id}
INFO: Bundle prepared for config: {config_id}
INFO: Bundle cached for config: {config_id}
INFO: Created AmplifierSession: {session_id}
INFO: Created session: {session_id} from config: {config_id}
```

---

### 6.2 Verify Session was Created

```bash
curl http://localhost:8765/sessions/{session_id}
```

**Expected:**
```json
{
  "session_id": "s1a2b3c4-5d6e-7f8g-9h0i-1j2k3l4m5n6o",
  "config_id": "c7a3f9e2-1b4d-4c8a-9f2e-d6b8a1c5e3f7",
  "status": "active"
}
```

---

### 6.3 List Sessions

```bash
curl http://localhost:8765/sessions?limit=10&offset=0
```

**Expected:**
```json
{
  "sessions": [
    {
      "session_id": "...",
      "config_id": "...",
      "status": "active",
      "message_count": 0,
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "total": 1
}
```

---

## Step 7: Test Session Messaging (Full Integration)

### 7.1 Send a Message
```bash
curl -X POST http://localhost:8765/sessions/{session_id}/messages \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello! What is 2 + 2?"
  }'
```

**Expected (Success):**
```json
{
  "session_id": "...",
  "response": "Hello! 2 + 2 equals 4.",
  "metadata": {
    "config_id": "..."
  }
}
```

**What This Tests:**
- Session retrieval works
- AmplifierSession execution works
- Transcript updates correctly
- Response generation succeeds

---

### 7.2 Verify Message Count Updated
```bash
curl http://localhost:8765/sessions/{session_id}
```

**Expected:**
```json
{
  "session_id": "...",
  "config_id": "...",
  "status": "active",
  "message_count": 1  ← Should be 1 now
}
```

---

## Step 8: Test Config Reusability

### 8.1 Create Second Session from Same Config
```bash
curl -X POST http://localhost:8765/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "config_id": "{same_config_id}"
  }'
```

**Expected:**
- Returns different session_id
- Same config_id
- Much faster (bundle already cached!)

**Expected Log:**
```
INFO: Using cached bundle for config: {config_id}
```

This proves bundle caching works!

---

### 8.2 Verify Both Sessions Exist
```bash
curl http://localhost:8765/sessions
```

**Expected:** Two sessions with same config_id, different session_ids

---

## Step 9: Test Session Resume

### 9.1 Get a Session ID
```bash
# List sessions and pick one
curl http://localhost:8765/sessions | jq '.sessions[0].session_id'
```

### 9.2 Resume the Session
```bash
curl -X POST http://localhost:8765/sessions/{session_id}/resume
```

**Expected:**
```json
{
  "session_id": "...",
  "config_id": "...",
  "status": "active",
  "message": "Session resumed successfully"
}
```

**What This Tests:**
- Session loading from database
- Config loading and bundle preparation
- Transcript restoration

---

## Step 10: Test Session Deletion

```bash
curl -X DELETE http://localhost:8765/sessions/{session_id}
```

**Expected:**
```json
{
  "message": "Session deleted successfully"
}
```

**Verify Deletion:**
```bash
curl http://localhost:8765/sessions/{session_id}
```

**Expected:** HTTP 404 - Session not found

---

## Step 11: Test Config Deletion

### 11.1 Create Sessions are Not Affected (Yet)
```bash
# Try to delete a config that has active sessions
curl -X DELETE http://localhost:8765/configs/{config_id}
```

**Expected:** 
- Currently: Succeeds (no FK constraint enforcement in code)
- Future: May want to prevent deleting configs with active sessions

---

### 11.2 Delete Config
```bash
curl -X DELETE http://localhost:8765/configs/{config_id}
```

**Expected:**
```json
{
  "message": "Config deleted successfully"
}
```

**Verify:**
```bash
curl http://localhost:8765/configs/{config_id}
```

**Expected:** HTTP 404 - Config not found

---

## Step 12: Test Error Cases

### 12.1 Create Session with Non-existent Config
```bash
curl -X POST http://localhost:8765/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "config_id": "non-existent-config-id"
  }'
```

**Expected:** HTTP 404 with "Config not found" error

---

### 12.2 Send Message to Non-existent Session
```bash
curl -X POST http://localhost:8765/sessions/fake-session-id/messages \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello"
  }'
```

**Expected:** HTTP 404 with "Session not found" error

---

### 12.3 Update Non-existent Config
```bash
curl -X PUT http://localhost:8765/configs/fake-config-id \
  -H "Content-Type: application/json" \
  -d '{
    "name": "new-name"
  }'
```

**Expected:** HTTP 404 with "Config not found" error

---

## Step 13: Test Pagination

### 13.1 Create Multiple Configs
```bash
for i in {1..5}; do
  curl -X POST http://localhost:8765/configs \
    -H "Content-Type: application/json" \
    -d "{
      \"name\": \"test-config-$i\",
      \"yaml_content\": \"bundle:\n  name: test-$i\nincludes:\n  - bundle: foundation\"
    }"
done
```

### 13.2 Test Pagination
```bash
# First page
curl "http://localhost:8765/configs?limit=2&offset=0"

# Second page
curl "http://localhost:8765/configs?limit=2&offset=2"

# Third page
curl "http://localhost:8765/configs?limit=2&offset=4"
```

**Verify:**
- Each page returns max 2 configs
- Total count is accurate
- Configs are ordered by updated_at DESC (newest first)

---

## Step 14: Integration Test - Complete Flow

This is the **end-to-end test** of the entire architecture.

### 14.1 Create Config
```bash
CONFIG_RESPONSE=$(curl -X POST http://localhost:8765/configs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "e2e-test",
    "yaml_content": "bundle:\n  name: e2e-test\n\nincludes:\n  - bundle: foundation\n\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: ${ANTHROPIC_API_KEY}\n      model: claude-sonnet-4-5\n\nsession:\n  orchestrator: loop-basic\n  context: context-simple"
  }')

CONFIG_ID=$(echo $CONFIG_RESPONSE | jq -r '.config_id')
echo "Created config: $CONFIG_ID"
```

### 14.2 Create Session from Config
```bash
SESSION_RESPONSE=$(curl -X POST http://localhost:8765/sessions \
  -H "Content-Type: application/json" \
  -d "{
    \"config_id\": \"$CONFIG_ID\"
  }")

SESSION_ID=$(echo $SESSION_RESPONSE | jq -r '.session_id')
echo "Created session: $SESSION_ID"
```

### 14.3 Send Message
```bash
curl -X POST http://localhost:8765/sessions/$SESSION_ID/messages \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the capital of France?"
  }' | jq
```

**Expected:** Valid response from AI

### 14.4 Create Second Session (Test Caching)
```bash
SESSION_2_RESPONSE=$(curl -X POST http://localhost:8765/sessions \
  -H "Content-Type: application/json" \
  -d "{
    \"config_id\": \"$CONFIG_ID\"
  }")

SESSION_2_ID=$(echo $SESSION_2_RESPONSE | jq -r '.session_id')
echo "Created second session: $SESSION_2_ID"
```

**Check logs:** Should see "Using cached bundle for config"

### 14.5 Verify Both Sessions Use Same Config
```bash
curl http://localhost:8765/sessions/$SESSION_ID | jq '{session_id, config_id}'
curl http://localhost:8765/sessions/$SESSION_2_ID | jq '{session_id, config_id}'
```

**Expected:** Same config_id, different session_ids

### 14.6 Cleanup
```bash
curl -X DELETE http://localhost:8765/sessions/$SESSION_ID
curl -X DELETE http://localhost:8765/sessions/$SESSION_2_ID
curl -X DELETE http://localhost:8765/configs/$CONFIG_ID
```

---

## Verification Checklist

After completing all steps, verify:

### Config Operations ✅
- [ ] Can create config with valid YAML
- [ ] Can retrieve config by ID
- [ ] Can list configs with pagination
- [ ] Can update config name/description/tags
- [ ] Can update config YAML content
- [ ] Invalid YAML is rejected with clear error
- [ ] Can delete config
- [ ] Programmatic helpers work (add tool/provider/bundle)

### Session Operations ✅
- [ ] Can create session from config_id
- [ ] Can list sessions
- [ ] Can retrieve session by ID
- [ ] Can resume session
- [ ] Can delete session
- [ ] Error when config_id doesn't exist
- [ ] Error when session_id doesn't exist

### Integration ✅
- [ ] Config → Session creation works
- [ ] Multiple sessions can share same config
- [ ] Bundle caching works (check logs)
- [ ] Message sending works
- [ ] Transcript updates correctly
- [ ] Session message_count increments

---

## Common Issues & Troubleshooting

### Issue: "Could not import amplifier-core"
**Cause:** Paths in .env are incorrect

**Fix:**
```bash
# Check paths exist
ls $AMPLIFIER_CORE_PATH
ls $AMPLIFIER_FOUNDATION_PATH

# Update .env with correct paths
vim .env
```

---

### Issue: "Bundle preparation timed out"
**Cause:** Network issues downloading remote modules

**Fix:**
- Check internet connection
- Verify module source URLs are accessible
- Increase timeout in session_manager.py if needed

---

### Issue: "Config not found" when creating session
**Cause:** config_id is wrong or config was deleted

**Fix:**
```bash
# List all configs to get valid IDs
curl http://localhost:8765/configs | jq '.configs[].config_id'
```

---

### Issue: HTTP 500 when creating session
**Cause:** Bundle preparation failed

**Check:**
1. Server logs for detailed error
2. YAML syntax in config
3. Bundle includes are resolvable
4. Module sources are accessible

---

## Quick Test Script

Create `quick_test.sh`:

```bash
#!/bin/bash
set -e

API="http://localhost:8765"

echo "1. Creating config..."
CONFIG=$(curl -s -X POST $API/configs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "quick-test",
    "yaml_content": "bundle:\n  name: quick-test\nincludes:\n  - bundle: foundation\nproviders:\n  - module: provider-anthropic\n    config:\n      api_key: test-key\n      model: claude-sonnet-4-5\nsession:\n  orchestrator: loop-basic\n  context: context-simple"
  }')

CONFIG_ID=$(echo $CONFIG | jq -r '.config_id')
echo "✓ Config created: $CONFIG_ID"

echo ""
echo "2. Listing configs..."
curl -s "$API/configs?limit=5" | jq '.configs[] | {name, config_id}'

echo ""
echo "3. Getting config..."
curl -s "$API/configs/$CONFIG_ID" | jq '{name, config_id, tags}'

echo ""
echo "4. Updating config..."
curl -s -X PUT "$API/configs/$CONFIG_ID" \
  -H "Content-Type: application/json" \
  -d '{"description": "Updated via script"}' | jq '{name, description}'

echo ""
echo "5. Cleanup..."
curl -s -X DELETE "$API/configs/$CONFIG_ID"
echo "✓ Config deleted"

echo ""
echo "All tests passed! ✅"
```

Make executable and run:
```bash
chmod +x quick_test.sh
./quick_test.sh
```

---

## Expected Success Path

If everything works correctly, you should be able to:

1. ✅ Start the service without errors
2. ✅ Create configs with YAML
3. ✅ List and retrieve configs
4. ✅ Update configs (YAML + metadata)
5. ✅ Use programmatic helpers
6. ✅ Create sessions from configs
7. ✅ Send messages to sessions
8. ✅ Multiple sessions share same config (bundle cached)
9. ✅ Delete sessions and configs

---

## Next Steps After Manual Testing

Once manual testing passes:

1. **Update existing test suite** - Adapt tests to new architecture
2. **Add integration tests** - Test Config → Session → Message flow
3. **Update documentation** - API docs, guides
4. **Create migration script** - For existing data (if needed)

---

## Summary

This architecture achieves:

- **Clarity**: Two primitives (Config, Session)
- **Reusability**: One config → many sessions
- **Efficiency**: Bundle caching by config_id
- **Simplicity**: No temp files, direct YAML → Bundle conversion
- **Type Safety**: Full Pydantic validation throughout

**Test the flow:** Config → Bundle.from_dict() → prepare() → AmplifierSession → messages
