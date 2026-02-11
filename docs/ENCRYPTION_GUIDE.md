# API Key Encryption Guide

## Overview

The Amplifier API implements encryption for sensitive configuration fields (API keys, secrets, tokens, etc.) to protect them at rest in the database and in transit when accessed via the API.

## Architecture

### Encryption Flow

```
┌─────────────┐
│     APP     │
│  (CLI/Web)  │
└──────┬──────┘
       │
       │ 1. POST /configs (with plain or encrypted api_key)
       ▼
┌─────────────────────────────────────────────────────┐
│               API Layer (FastAPI)                    │
│  - Receives config with plain or encrypted keys      │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ 2. ConfigManager.create_config()
                   ▼
┌─────────────────────────────────────────────────────┐
│           Config Manager (Business Logic)            │
│  - Validates config structure                        │
│  - Encrypts sensitive fields (if not already)        │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ 3. Store encrypted JSON
                   ▼
┌─────────────────────────────────────────────────────┐
│              Database (PostgreSQL)                   │
│  - Stores config with encrypted keys                 │
│  - Keys have "enc:" prefix                           │
└─────────────────────────────────────────────────────┘
```

### Retrieval Flow - Two Modes

#### Mode 1: Encrypted (for Apps) - **DEFAULT**
```
GET /configs/{id}?decrypt=false
                   │
                   ▼
        ┌──────────────────┐
        │  ConfigManager   │
        │  decrypt=False   │
        └────────┬─────────┘
                 │
                 ▼
        Returns: {"api_key": "enc:gAAAAA..."}
```

#### Mode 2: Decrypted (for Sessions/Admin)
```
GET /configs/{id}?decrypt=true
                   │
                   ▼
        ┌──────────────────┐
        │  ConfigManager   │
        │  decrypt=True    │
        └────────┬─────────┘
                 │
                 ▼
        Returns: {"api_key": "sk-ant-xxx..."}
```

#### Mode 3: Internal Session Creation
```
SessionManager.create_session(config_id)
                   │
                   ▼
        ┌──────────────────┐
        │  get_config()    │
        │  decrypt=True    │ (always decrypted for providers)
        └────────┬─────────┘
                 │
                 ▼
        Passes plain key to Provider
```

## Implementation Details

### Encryption Module

**File:** `amplifier_app_api/core/secrets_encryption.py`

**Features:**
- Uses **Fernet** (symmetric encryption) from the `cryptography` library
- **Key Derivation:** PBKDF2-HMAC-SHA256 with 100,000 iterations
- **Encryption Key:** Loaded from `CONFIG_ENCRYPTION_KEY` environment variable
- **Field Detection:** Automatically encrypts fields matching patterns:
  - `api_key`
  - `secret`
  - `password`
  - `token`
  - `credential`
  - `private_key`
  - `access_key`
- **Prefix Convention:** Encrypted values have `enc:` prefix
- **Skip Patterns:**
  - Already encrypted values (has `enc:` prefix)
  - Environment variable references (`${VAR_NAME}`)

**Example:**
```python
# Plain text
{"api_key": "sk-ant-abc123"}

# After encryption
{"api_key": "enc:gAAAAABl1K2N...base64data..."}
```

### API Endpoints

#### 1. Create Config - `POST /configs`

**Behavior:**
- Accepts plain text or pre-encrypted API keys
- Automatically encrypts sensitive fields before storage
- **Returns:** Decrypted config (original input)

**Example:**
```json
// Request
{
  "name": "my-config",
  "config_data": {
    "providers": [{
      "config": {"api_key": "sk-ant-abc123"}
    }]
  }
}

// Response (decrypted)
{
  "config_id": "uuid",
  "config_data": {
    "providers": [{
      "config": {"api_key": "sk-ant-abc123"}
    }]
  },
  "encrypted": false
}
```

#### 2. Get Config - `GET /configs/{id}?decrypt=false`

**Behavior:**
- **Default (`decrypt=false`):** Returns encrypted keys (secure for apps)
- **Optional (`decrypt=true`):** Returns decrypted keys (admin/debugging)

**Examples:**

**Encrypted Response (Default):**
```bash
GET /configs/abc123?decrypt=false
```
```json
{
  "config_id": "abc123",
  "config_data": {
    "providers": [{
      "config": {"api_key": "enc:gAAAAABl1K2N..."}
    }]
  },
  "encrypted": true
}
```

**Decrypted Response:**
```bash
GET /configs/abc123?decrypt=true
```
```json
{
  "config_id": "abc123",
  "config_data": {
    "providers": [{
      "config": {"api_key": "sk-ant-abc123"}
    }]
  },
  "encrypted": false
}
```

#### 3. Update Config - `PUT /configs/{id}`

**Behavior:**
- Same as create: encrypts before storage
- **Returns:** Decrypted config

#### 4. Delete Config - `DELETE /configs/{id}`

**Behavior:**
- Deletes config from database (encrypted data is removed)

## Security Best Practices

### 1. Environment Key Management

**Development:**
```bash
# .env
CONFIG_ENCRYPTION_KEY=your-secret-key-here-min-32-chars
```

**Production:**
- Use AWS Secrets Manager, Azure Key Vault, or HashiCorp Vault
- Never commit keys to version control
- Rotate keys periodically

### 2. App-Side Encryption (Recommended)

Apps should encrypt sensitive fields **before** sending to the API:

```python
from amplifier_app_api.core.secrets_encryption import ConfigEncryption

# In your app
encryptor = ConfigEncryption(os.environ["CONFIG_ENCRYPTION_KEY"])

config = {
    "providers": [{
        "config": {"api_key": "sk-ant-abc123"}
    }]
}

# Encrypt before sending
encrypted_config = encryptor.encrypt_config(config)

# Send to API
response = requests.post("/configs", json={
    "name": "my-config",
    "config_data": encrypted_config
})
```

### 3. App-Side Decryption

When retrieving configs with encrypted keys:

```python
# Retrieve encrypted config
response = requests.get("/configs/abc123?decrypt=false")
config_data = response.json()["config_data"]

# Decrypt locally
encryptor = ConfigEncryption(os.environ["CONFIG_ENCRYPTION_KEY"])
decrypted_config = encryptor.decrypt_config(config_data)

# Now use the plain API key
api_key = decrypted_config["providers"][0]["config"]["api_key"]
```

### 4. Internal Session Use

The `SessionManager` always retrieves **decrypted** configs internally:

```python
# In session_manager.py
config = await self.config_manager.get_config(config_id, decrypt=True)
# Passes plain keys to providers
```

This is secure because:
- Keys are only decrypted in-memory within the backend
- Never exposed via external API (unless explicitly requested)
- Keys are passed directly to providers without network transit

## Swagger UI Testing

The Swagger UI at `/docs` allows you to toggle between encrypted and decrypted views:

1. **Create a config:**
   - Go to `POST /configs`
   - Provide config with plain API key
   - Click "Execute"

2. **View encrypted:**
   - Go to `GET /configs/{id}`
   - Set `decrypt = false`
   - Click "Execute"
   - See: `"api_key": "enc:gAAAAA..."`
   - Response shows: `"encrypted": true`

3. **View decrypted:**
   - Same endpoint
   - Set `decrypt = true`
   - Click "Execute"
   - See: `"api_key": "sk-ant-..."`
   - Response shows: `"encrypted": false`

## Security Considerations & Limitations

### Current Implementation

**✅ Strengths:**
- Encryption at rest (database)
- Automatic field detection
- Easy to use
- Supports pre-encrypted values
- Clear indication of encryption state

**⚠️ Limitations:**

1. **Fixed Salt:** Uses `amplifier-config-salt` which makes key rotation difficult
   - **Impact:** If key is compromised, re-encrypting all configs is complex
   - **Mitigation:** Use per-config random salts in future versions

2. **Same Key for All Users:** All configs use the same encryption key
   - **Impact:** If key leaks, all API keys are compromised
   - **Mitigation:** Consider per-user or per-tenant keys

3. **No Key Rotation Strategy:** No built-in mechanism to rotate encryption keys
   - **Impact:** Cannot easily change encryption keys without manual migration
   - **Mitigation:** Plan key rotation procedure (decrypt all → re-encrypt with new key)

4. **Symmetric Encryption:** Uses same key for encryption and decryption
   - **Impact:** Anyone with the key can both encrypt and decrypt
   - **Mitigation:** Use asymmetric encryption (RSA) for apps (public key to encrypt, private key to decrypt in backend)

5. **No Audit Trail:** Doesn't log when decrypted configs are accessed
   - **Impact:** Cannot detect unauthorized access to sensitive data
   - **Mitigation:** Add audit logging for `decrypt=true` API calls

### Recommended Enhancements

**For Production:**

1. **Use Per-Config Salts:**
   ```python
   # Store salt with encrypted data
   {"api_key": "enc:salt:base64salt:cipher:base64cipher"}
   ```

2. **Implement Audit Logging:**
   ```python
   if decrypt:
       audit_log.info(f"User {user_id} decrypted config {config_id}")
   ```

3. **Add Permission Checks:**
   ```python
   if decrypt and not user.has_permission("decrypt_configs"):
       raise HTTPException(403, "Insufficient permissions")
   ```

4. **Key Rotation Support:**
   ```python
   # Add version to encrypted values
   {"api_key": "enc:v2:..."}
   # Support multiple key versions during rotation
   ```

5. **Consider Asymmetric Encryption:**
   - Apps encrypt with public key
   - Backend decrypts with private key
   - Apps cannot decrypt (more secure)

## Testing

**Unit Tests:** `tests/test_encryption.py` (to be created)

**Manual Testing:**

1. Start the API: `uvicorn amplifier_app_api.main:app --reload`
2. Open Swagger UI: `http://localhost:8000/docs`
3. Create a config with an API key
4. Retrieve with `decrypt=false` → verify `enc:` prefix
5. Retrieve with `decrypt=true` → verify plain text
6. Create a session → verify session works (keys decrypted internally)

## Troubleshooting

### Error: "CONFIG_ENCRYPTION_KEY environment variable must be set"

**Cause:** Encryption key not configured

**Solution:**
```bash
export CONFIG_ENCRYPTION_KEY="your-secret-key-min-32-chars"
```

### Error: "Failed to decrypt field"

**Cause:**
- Wrong encryption key
- Corrupted encrypted data
- Key changed after encryption

**Solution:**
- Verify `CONFIG_ENCRYPTION_KEY` matches the one used for encryption
- Check if key was rotated (use previous key to decrypt)
- Re-create config if data is corrupted

### Config decrypted when it shouldn't be

**Cause:** `decrypt=true` used in API call

**Solution:**
- Ensure apps use `decrypt=false` (default)
- Check API calls in app code

### Session creation fails with "Invalid API key"

**Cause:** Keys are encrypted when passed to provider

**Solution:**
- Verify `SessionManager` uses `decrypt=True` when getting configs
- Check `session_manager.py` line 186 and 268

## Summary

The encryption system provides a solid foundation for protecting sensitive configuration data:

- **At Rest:** Data encrypted in database ✅
- **In Transit:** Encrypted by default in API responses ✅
- **In Use:** Decrypted only when needed (session creation) ✅
- **Flexible:** Swagger UI toggle for debugging ✅

For production use, consider implementing the recommended enhancements for key rotation, audit logging, and per-user encryption.
