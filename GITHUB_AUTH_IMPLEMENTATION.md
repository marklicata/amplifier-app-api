# GitHub Auth in Dev Mode - Implementation Summary

## Overview

Successfully implemented GitHub CLI authentication fallback for development mode. When `AUTH_REQUIRED=false`, the system now uses your GitHub username (from `gh` CLI) instead of hardcoded `"dev-user"`.

## What Was Changed

### 1. **Configuration** (`amplifier_app_api/config.py`)

Added new setting:
```python
use_github_auth_in_dev: bool = Field(
    default=True,
    description="Use GitHub CLI (gh) for user_id when auth is disabled (falls back to 'dev-user')",
)
```

**Default**: `True` (enabled by default)

### 2. **Auth Middleware** (`amplifier_app_api/middleware/auth.py`)

Added GitHub username detection:

**New method**: `_get_github_user()`
- Runs `gh api user --jq .login` to get GitHub username
- Caches result to avoid repeated subprocess calls
- 2-second timeout for responsiveness
- Graceful fallback to `"dev-user"` on any error

**Updated dev mode logic**:
```python
if not settings.auth_required:
    request.state.app_id = "dev-app"

    # Use GitHub CLI to get user_id if enabled
    if settings.use_github_auth_in_dev:
        request.state.user_id = await self._get_github_user()
    else:
        request.state.user_id = "dev-user"
```

### 3. **Test Suite** (`tests/test_auth_middleware.py`)

Added 6 new comprehensive tests:

1. ✅ `test_github_auth_in_dev_mode_with_gh_cli` - Successful gh CLI usage
2. ✅ `test_github_auth_fallback_when_gh_cli_fails` - gh returns error
3. ✅ `test_github_auth_fallback_on_timeout` - gh times out
4. ✅ `test_github_auth_disabled_uses_dev_user` - Feature disabled
5. ✅ `test_github_auth_cache_reused` - Caching works correctly
6. ✅ `test_github_auth_with_file_not_found` - gh not installed

All tests use mocking to avoid requiring actual `gh` CLI installation.

### 4. **Documentation Updates**

**Updated files**:
- ✅ `docs/TESTING_AUTHENTICATION.md` - Added GitHub auth section and usage examples
- ✅ `README.md` - Updated authentication setup section
- ✅ `QUICKSTART.md` - Added USE_GITHUB_AUTH_IN_DEV to config example
- ✅ `.env.example` - Added USE_GITHUB_AUTH_IN_DEV setting

## How It Works

### Flow Diagram

```
Request with AUTH_REQUIRED=false
│
├─> USE_GITHUB_AUTH_IN_DEV=true?
│   │
│   ├─> YES: Try to get GitHub username
│   │   │
│   │   ├─> Check cache
│   │   │   └─> If cached: Return cached value ✓
│   │   │
│   │   ├─> Run: gh api user --jq .login (2s timeout)
│   │   │   │
│   │   │   ├─> Success: Cache and return username ✓
│   │   │   ├─> Timeout: Fallback to "dev-user"
│   │   │   ├─> FileNotFoundError: Fallback to "dev-user"
│   │   │   └─> Other error: Fallback to "dev-user"
│   │
│   └─> NO: Use "dev-user" directly
│
└─> Set request.state.user_id
```

### Cache Behavior

- **First request**: Runs `gh` CLI subprocess
- **Subsequent requests**: Uses cached value (no subprocess overhead)
- **Cache persistence**: Process-level (resets on server restart)
- **Cache key**: Global module-level variable

## Benefits

✅ **Real user identities** - Each developer automatically gets their own `user_id`
✅ **Zero configuration** - Works if `gh auth login` already done
✅ **Better testing** - Test multi-user scenarios locally
✅ **Graceful fallback** - Works offline/without gh CLI
✅ **Performance** - Cached result, minimal overhead
✅ **Configurable** - Can disable with `USE_GITHUB_AUTH_IN_DEV=false`

## Usage

### For Developers

**If you're logged into GitHub CLI:**
```bash
# Check your GitHub auth status
gh auth status

# Your username will be used automatically
# Example: If your GitHub username is "marklicata"
# → All sessions will have owner_user_id="marklicata"
```

**If you want to use "dev-user" instead:**
```bash
# Add to .env file
USE_GITHUB_AUTH_IN_DEV=false
```

**First time setup:**
```bash
# Install GitHub CLI (if not already installed)
# macOS: brew install gh
# Windows: winget install GitHub.cli

# Login to GitHub
gh auth login

# Verify it works
gh api user --jq .login
# Should output your GitHub username
```

### For Testing

Tests can mock the GitHub user detection:

```python
from amplifier_app_api.middleware import auth

# Clear cache before test
auth._github_user_cache = None

# Mock subprocess
mock_process = AsyncMock()
mock_process.returncode = 0
mock_process.communicate = AsyncMock(return_value=(b"test-user\n", b""))

with patch("asyncio.create_subprocess_exec", return_value=mock_process):
    # Test code here
    pass
```

## Configuration Reference

### Environment Variables

```bash
# Enable/disable the feature
USE_GITHUB_AUTH_IN_DEV=true  # default: true

# Must be false for feature to activate
AUTH_REQUIRED=false  # default: false
```

### Precedence

1. If `AUTH_REQUIRED=true` → Use JWT authentication (GitHub auth ignored)
2. If `AUTH_REQUIRED=false` and `USE_GITHUB_AUTH_IN_DEV=true` → Use GitHub username
3. If `AUTH_REQUIRED=false` and `USE_GITHUB_AUTH_IN_DEV=false` → Use "dev-user"

## Error Handling

All errors result in graceful fallback to `"dev-user"`:

| Error Type | Cause | Fallback |
|------------|-------|----------|
| `FileNotFoundError` | gh CLI not installed | "dev-user" |
| `TimeoutError` | gh CLI took >2s | "dev-user" |
| Return code != 0 | gh not logged in / auth failed | "dev-user" |
| Empty stdout | gh returned no output | "dev-user" |
| Any exception | Unexpected error | "dev-user" |

## Performance Impact

- **First request**: +2ms - 2000ms (depends on gh CLI speed, max 2s timeout)
- **Subsequent requests**: ~0ms (cached)
- **Recommended**: Pre-warm cache by making a test request on startup

## Future Enhancements

Potential improvements (not implemented):

1. **Cache invalidation** - Add TTL or manual cache refresh endpoint
2. **Alternative providers** - Support other Git providers (GitLab, Bitbucket)
3. **Git config fallback** - Use `git config user.name` if gh CLI fails
4. **Health check** - Add endpoint to verify GitHub auth status
5. **Metrics** - Track cache hit rate and gh CLI success rate

## Testing

### Running the Tests

```bash
# Run all auth tests
pytest tests/test_auth_middleware.py -v

# Run only GitHub auth tests
pytest tests/test_auth_middleware.py -k "github" -v

# Run with coverage
pytest tests/test_auth_middleware.py --cov=amplifier_app_api.middleware.auth --cov-report=term
```

### Manual Testing

```bash
# 1. Start the server (auth disabled by default)
python -m amplifier_app_api.main

# 2. Make a request
curl http://localhost:8765/sessions

# 3. Check logs - you should see:
#    "Using GitHub user from gh CLI: <your-username>"
#    OR
#    "Falling back to 'dev-user'"
```

## Rollback Plan

If issues arise, disable the feature:

```bash
# Option 1: Environment variable
export USE_GITHUB_AUTH_IN_DEV=false

# Option 2: .env file
echo "USE_GITHUB_AUTH_IN_DEV=false" >> .env

# Option 3: Revert code changes
git revert <commit-hash>
```

The feature is **fully backward compatible** - existing behavior (`"dev-user"`) can be restored by setting the flag to `false`.

## Summary

✨ **Successfully implemented GitHub CLI authentication for development mode**
📝 **Comprehensive test coverage with 6 new tests**
📚 **Updated documentation across 4 files**
🔒 **Safe with graceful fallbacks and error handling**
⚡ **Performant with request-level caching**
🎯 **Zero-config for developers already using GitHub CLI**

---

**Implementation Date**: 2026-02-11
**Feature Status**: ✅ Ready for use
**Breaking Changes**: None (fully backward compatible)
