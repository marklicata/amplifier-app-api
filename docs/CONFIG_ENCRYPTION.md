# Config Encryption

## Overview

The API automatically encrypts sensitive fields in stored configurations to protect API keys, secrets, passwords, and other credentials at rest.

## How It Works

### Automatic Encryption

When you create or update a config, the system automatically:

1. **Detects sensitive fields** - Looks for field names containing:
   - `api_key`
   - `secret`
   - `password`
   - `token`
   - `credential`
   - `private_key`
   - `access_key`

2. **Encrypts values** - Uses Fernet symmetric encryption with authenticated encryption (prevents tampering)

3. **Stores securely** - Encrypted values are prefixed with `enc:` and stored in the database

4. **Decrypts on retrieval** - When you GET a config, sensitive fields are automatically decrypted

### What Gets Encrypted

```json
{
  "providers": [
    {
      "module": "provider-anthropic",
      "config": {
        "api_key": "sk-ant-1234567890",    // ← ENCRYPTED
        "model": "claude-sonnet-4-5"        // ← NOT encrypted
      }
    }
  ],
  "auth": {
    "secret": "my-secret-token",           // ← ENCRYPTED
    "timeout": 30                          // ← NOT encrypted
  }
}
```

### Environment Variables

Environment variable references are **NOT encrypted** and work exactly as before:

```json
{
  "config": {
    "api_key": "${ANTHROPIC_API_KEY}"     // ← NOT encrypted (env var reference)
  }
}
```

## Setup

### 1. Generate Encryption Key

```bash
# Generate a secure random key
openssl rand -hex 32
```

### 2. Configure Environment Variable

Add to your `.env` file:

```bash
CONFIG_ENCRYPTION_KEY=your-generated-key-here
```

### 3. Restart Service

```bash
./run-dev.sh
```

The service will log:
```
INFO: Config encryption enabled
```

If the key is not set:
```
WARNING: CONFIG_ENCRYPTION_KEY not set - configs will be stored in plain text
```

## Security Considerations

### Key Management

**Production Deployment:**
- Store `CONFIG_ENCRYPTION_KEY` in Azure Key Vault, AWS Secrets Manager, or similar
- Use unique keys per environment (dev/staging/production)
- Rotate keys periodically using key versioning
- Never commit encryption keys to git

**Key Rotation:**
If you need to rotate the encryption key:
1. Keep the old key available temporarily
2. Set new key in environment
3. Retrieve and re-save all configs (triggers re-encryption with new key)
4. Remove old key once all configs are migrated

### What This Protects

✅ **Database dumps** - Encrypted fields remain secure even if database is compromised  
✅ **Backups** - Backup files contain encrypted values  
✅ **Logs** - Encrypted values won't leak into logs  
✅ **Admin access** - DBAs can't read API keys without the encryption key  

### What This Doesn't Protect

❌ **Runtime memory** - Decrypted values exist in memory during processing  
❌ **Transport** - Use HTTPS/TLS for data in transit  
❌ **Application compromise** - If the service is compromised, the encryption key can be accessed  
❌ **Environment variables** - Values in env vars are not encrypted  

## API Behavior

### Creating Configs

```bash
curl -X POST http://localhost:8765/configs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-config",
    "config_data": {
      "providers": [{
        "config": {
          "api_key": "sk-ant-1234567890"
        }
      }]
    }
  }'
```

**What happens:**
- API key is encrypted before storage
- Response shows the **decrypted** value (for convenience)
- Database contains `"api_key": "enc:gAAAAAB..."`

### Retrieving Configs

```bash
curl http://localhost:8765/configs/{config_id}
```

**What happens:**
- Config is retrieved from database
- Encrypted fields are automatically decrypted
- Response contains original plaintext values

### Updating Configs

```bash
curl -X PUT http://localhost:8765/configs/{config_id} \
  -H "Content-Type: application/json" \
  -d '{
    "config_data": {
      "providers": [{
        "config": {
          "api_key": "sk-ant-new-key-9876"
        }
      }]
    }
  }'
```

**What happens:**
- New API key is encrypted before storage
- Old encrypted value is replaced
- Response shows the **decrypted** new value

## Troubleshooting

### "CONFIG_ENCRYPTION_KEY environment variable must be set"

**Cause:** The encryption key is not configured.

**Fix:**
1. Generate a key: `openssl rand -hex 32`
2. Add to `.env`: `CONFIG_ENCRYPTION_KEY=your-key-here`
3. Restart service

### "Failed to decrypt field X"

**Cause:** The encryption key has changed or the stored value is corrupted.

**Fix:**
- Restore the original encryption key
- If key is permanently lost, you'll need to:
  1. Delete the config and recreate it
  2. Re-enter the API keys manually

### Configs created before encryption are in plain text

**Fix:**
1. Retrieve the config: `GET /configs/{id}`
2. Update it with the same data: `PUT /configs/{id}`
3. The update will encrypt any sensitive fields

## Implementation Details

### Encryption Algorithm

- **Algorithm:** Fernet (AES-128-CBC + HMAC-SHA256)
- **Key Derivation:** PBKDF2-HMAC-SHA256 (100,000 iterations)
- **Salt:** Fixed per deployment (in production, use unique per-environment)
- **Format:** `enc:{base64-encoded-fernet-token}`

### Field Detection

Field names are checked case-insensitively against these patterns:
```python
SENSITIVE_FIELD_PATTERNS = [
    r"api_key",
    r"secret",
    r"password",
    r"token",
    r"credential",
    r"private_key",
    r"access_key",
]
```

### Nested Configs

Encryption works recursively through nested objects and arrays:

```json
{
  "providers": [
    { "config": { "api_key": "..." } },  // ← Encrypted
    { "config": { "api_key": "..." } }   // ← Encrypted
  ]
}
```

## Testing

Run encryption tests:

```bash
# Run encryption-specific tests
python -m pytest tests/test_secrets_encryption.py -v

# Run all tests including encryption
python -m pytest tests/ -v
```

Test coverage includes:
- Basic encryption/decryption
- Environment variable preservation
- Multiple sensitive field types
- Nested configurations
- Double-encryption prevention
- Case-insensitive field detection
- Error handling

## Migration Guide

### Existing Deployments

If you're adding encryption to an existing deployment with configs already stored:

1. **Set encryption key:**
   ```bash
   export CONFIG_ENCRYPTION_KEY=$(openssl rand -hex 32)
   ```

2. **Restart service** - Existing configs will work (decryption handles plain text gracefully)

3. **Migrate configs** (optional but recommended):
   ```bash
   # Script to re-encrypt all configs
   for config_id in $(curl http://localhost:8765/configs | jq -r '.configs[].config_id'); do
     curl -X PUT http://localhost:8765/configs/$config_id \
       -H "Content-Type: application/json" \
       -d "$(curl http://localhost:8765/configs/$config_id)"
   done
   ```

### New Deployments

For fresh deployments:

1. Generate encryption key before first run
2. Set `CONFIG_ENCRYPTION_KEY` in environment
3. All configs will be encrypted from the start

## FAQ

**Q: Is encryption enabled by default?**  
A: No. You must set `CONFIG_ENCRYPTION_KEY` to enable encryption. Without it, configs are stored in plain text with a warning logged.

**Q: Can I disable encryption?**  
A: Yes. Remove `CONFIG_ENCRYPTION_KEY` from environment. Existing encrypted configs will fail to decrypt.

**Q: What happens if I lose the encryption key?**  
A: Encrypted configs become unreadable. You'll need to delete and recreate them. **Always back up your encryption key securely.**

**Q: Does this encrypt the entire config?**  
A: No. Only fields with sensitive names (api_key, secret, etc.) are encrypted. This allows:
- Efficient database queries on non-sensitive fields
- Smaller storage footprint
- Faster processing

**Q: Can I add custom sensitive field patterns?**  
A: Currently, patterns are hardcoded in `secrets_encryption.py`. You can modify `SENSITIVE_FIELD_PATTERNS` if needed.

**Q: Does this work with session runtime?**  
A: Yes. When a session is created from a config, the decrypted values are passed to the Amplifier session. The session uses the plaintext API keys as normal.

## Related Documentation

- [Authentication Design](./AUTHENTICATION_DESIGN.md) - User authentication
- [Setup Guide](./SETUP.md) - Production deployment
- [Manual Testing](./MANUAL_TESTING_GUIDE.md) - Testing configs
