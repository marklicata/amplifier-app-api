# Authentication & Authorization Design

> **✅ IMPLEMENTATION STATUS: COMPLETE**  
> This design has been fully implemented and deployed. Authentication is currently **in production** with `AUTH_REQUIRED=true`.  
> For testing and usage guide, see [TESTING_AUTHENTICATION.md](./TESTING_AUTHENTICATION.md).

---

## Overview

This service supports multi-tenant authentication where:
- **Applications** (identified by `app_id`) can call the service
- **Users** (identified by `user_id`) create and use sessions
- **Sessions** (identified by `session_id`) are owned by the user and accessible from any app
- `app_id` is tracked for auditing/analytics but doesn't restrict session access

## Authentication Methods

### Option 1: API Key + JWT (Recommended for MVP)

**Client sends:**
```http
POST /sessions HTTP/1.1
Host: api.example.com
X-API-Key: app_abc123_key_xyz789
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json

{
  "config_id": "c7a3f9e2..."
}
```

**Server validates:**
1. Check `X-API-Key` against registered applications → Extract `app_id`
2. Verify JWT signature and claims → Extract `user_id` from `sub` claim
3. Check JWT not expired, issuer is trusted
4. Create session owned by (`app_id`, `user_id`)

**Pros:**
- Simple to implement
- Clear separation: API key = app auth, JWT = user auth
- Works well with external auth providers (Auth0, Clerk, etc.)

**Cons:**
- Two credentials to manage
- Need secure key storage on client

### Option 2: JWT with Embedded App Claim

**Client sends:**
```http
POST /sessions HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json
```

**JWT payload:**
```json
{
  "sub": "user-123",
  "app_id": "my-app",
  "iss": "https://your-auth.example.com",
  "exp": 1738728000
}
```

**Server validates:**
1. Verify JWT signature (using issuer's public key)
2. Extract `app_id` and `user_id` (from `sub`) from verified claims
3. Create session owned by (`app_id`, `user_id`)

**Pros:**
- Single credential
- Standard OAuth 2.0 / OIDC flow
- Can leverage existing identity providers

**Cons:**
- More complex token issuance
- Requires coordination with auth provider to include `app_id` claim

### Option 3: Mutual TLS (mTLS)

For high-security enterprise deployments.

**Not recommended for MVP** - adds significant complexity.

## Data Model Changes

### Database Schema Updates

```sql
-- Add app_id and user_id to sessions table
ALTER TABLE sessions ADD COLUMN app_id VARCHAR(255) NOT NULL;
ALTER TABLE sessions ADD COLUMN user_id VARCHAR(255) NOT NULL;

-- Add composite index for efficient lookups
CREATE INDEX idx_sessions_app_user ON sessions(app_id, user_id);

-- Add unique constraint if needed (one active session per user per app)
-- CREATE UNIQUE INDEX idx_sessions_active_user ON sessions(app_id, user_id, status) 
--   WHERE status = 'active';

-- App registration table
CREATE TABLE applications (
    app_id VARCHAR(255) PRIMARY KEY,
    api_key_hash VARCHAR(255) NOT NULL,  -- bcrypt hash of API key
    app_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    settings JSONB  -- App-specific settings
);

-- User tracking (optional, for usage analytics)
CREATE TABLE users (
    user_id VARCHAR(255) PRIMARY KEY,
    app_id VARCHAR(255) NOT NULL,
    first_seen TIMESTAMP NOT NULL,
    last_seen TIMESTAMP NOT NULL,
    FOREIGN KEY (app_id) REFERENCES applications(app_id)
);
```

### Model Updates

```python
# amplifier_app_api/models/session.py
class Session(BaseModel):
    session_id: str
    config_id: str
    app_id: str  # NEW: Which application owns this
    user_id: str  # NEW: Which user owns this
    status: SessionStatus = SessionStatus.ACTIVE
    metadata: SessionMetadata
    transcript: list[dict[str, Any]] = Field(default_factory=list)

# amplifier_app_api/models/application.py (NEW)
class Application(BaseModel):
    app_id: str
    app_name: str
    api_key_hash: str  # Never store plain API keys
    is_active: bool = True
    created_at: datetime
    settings: dict[str, Any] = Field(default_factory=dict)
```

## API Changes

### Request Context

All authenticated endpoints will have access to:

```python
from fastapi import Request

@router.post("/sessions")
async def create_session(
    request: Request,
    session_request: SessionCreateRequest,
):
    # Authentication middleware sets these
    app_id: str = request.state.app_id  # For auditing/analytics only
    user_id: str = request.state.user_id
    
    # Sessions belong to the USER, not (app, user) pair
    # app_id is recorded for tracking which app created it
    session = await manager.create_session(
        config_id=session_request.config_id,
        user_id=user_id,
        created_by_app_id=app_id,  # Track but don't restrict
    )
    ...
```


### Authorization Rules

1. **Session Creation**: Any authenticated user can create sessions
2. **Session Access**: Users can only access **their own** sessions (not other users')
3. **Cross-App Access**: Users can access their sessions from **any app** they authenticate through
4. **Admin Operations**: Need separate admin API with higher privileges

```python
async def authorize_session_access(
    session_id: str,
    app_id: str,  # Only for logging/auditing
    user_id: str,
    db: Database,
) -> Session:
    """Verify user has access to this session."""
    session = await db.get_session(session_id)
    
    if not session:
        raise HTTPException(404, "Session not found")
    
    # ONLY check user_id - sessions belong to users, not (app, user) pairs
    if session.user_id != user_id:
        raise HTTPException(403, "Access denied: not your session")
    
    # Update last_accessed_by_app for analytics
    await db.update_session_access(session_id, app_id)
    
    return session
```

**Key Point:** `app_id` is recorded but NOT enforced. A user who creates a session in "Mobile App" can resume it in "Web App".

## Configuration

### Environment Variables

```bash
# Authentication mode
AUTH_MODE=api_key_jwt  # Options: none, api_key_jwt, jwt_only, mtls
AUTH_REQUIRED=true     # Can disable for local dev

# JWT Settings
JWT_ALGORITHM=RS256    # Use asymmetric for production
JWT_PUBLIC_KEY_URL=https://your-auth.example.com/.well-known/jwks.json
JWT_ISSUER=https://your-auth.example.com
JWT_AUDIENCE=amplifier-api

# API Key Settings
API_KEY_HEADER=X-API-Key
```

### Settings Model

```python
class Settings(BaseSettings):
    # ... existing fields ...
    
    # Authentication
    auth_mode: str = Field(
        default="api_key_jwt",
        description="Authentication mode: none, api_key_jwt, jwt_only, mtls"
    )
    auth_required: bool = Field(
        default=True,
        description="Require authentication (disable for local dev only)"
    )
    
    # JWT
    jwt_algorithm: str = Field(default="RS256")
    jwt_public_key_url: str | None = None
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    
    # API Keys
    api_key_header: str = Field(default="X-API-Key")
```

## Middleware Implementation

```python
# amplifier_app_api/middleware/auth.py

from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
import jwt

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip auth for health checks
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        if not settings.auth_required:
            # Dev mode: use default test user
            request.state.app_id = "dev-app"
            request.state.user_id = "dev-user"
            return await call_next(request)
        
        try:
            # Extract and verify credentials based on auth_mode
            if settings.auth_mode == "api_key_jwt":
                app_id = await self._verify_api_key(request)
                user_id = await self._verify_jwt(request)
            elif settings.auth_mode == "jwt_only":
                app_id, user_id = await self._verify_jwt_with_app_claim(request)
            else:
                raise HTTPException(401, "Authentication mode not configured")
            
            # Set authenticated context
            request.state.app_id = app_id
            request.state.user_id = user_id
            
            return await call_next(request)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise HTTPException(401, "Authentication failed")
    
    async def _verify_api_key(self, request: Request) -> str:
        """Verify API key and return app_id."""
        api_key = request.headers.get(settings.api_key_header)
        if not api_key:
            raise HTTPException(401, "API key required")
        
        # Look up app by API key hash
        app = await db.get_app_by_key_hash(hash_api_key(api_key))
        if not app or not app.is_active:
            raise HTTPException(401, "Invalid API key")
        
        return app.app_id
    
    async def _verify_jwt(self, request: Request) -> str:
        """Verify JWT and return user_id."""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(401, "Bearer token required")
        
        token = auth_header.split(" ")[1]
        
        # Verify JWT (fetch public keys from JWKS endpoint)
        payload = jwt.decode(
            token,
            options={"verify_signature": True},
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
        
        return payload["sub"]  # user_id from subject claim
```

## Migration Path

### Phase 1: Add Auth Infrastructure (No Enforcement)
- Add `app_id`, `user_id` columns to sessions (nullable)
- Add authentication middleware (disabled by default)
- Add Application model and table
- Set `AUTH_REQUIRED=false` in dev

### Phase 2: Enable Auth in Staging
- Set `AUTH_REQUIRED=true`
- Test with real API keys and JWTs
- Verify authorization rules

**About API Keys:**
Yes! Each **application** gets its own API key:
- "Mobile App" → API key `app_mobile_key_abc123`
- "Web App" → API key `app_web_key_xyz789`
- "Desktop App" → API key `app_desktop_key_def456`

When an app makes a request, it sends its API key in the `X-API-Key` header. Your service verifies the key and extracts the `app_id` (e.g., "mobile-app", "web-app"). This tells you **which application** is calling, but doesn't restrict which sessions that user can access.

### Phase 3: Migrate Existing Sessions
- Backfill `app_id="legacy"`, `user_id="system"` for old sessions
- Make columns NOT NULL

### Phase 4: Production Deployment
- Enable auth in production
- Monitor for auth failures
- Provide migration guide for API consumers

## Security Considerations

1. **API Key Storage**
   - Never store plain API keys in database
   - Use bcrypt with high work factor
   - Provide key rotation mechanism

2. **JWT Verification**
   - Always verify signature with public key
   - Check expiration, issuer, audience
   - Cache JWKS keys but refresh periodically

3. **Rate Limiting**
   - Rate limit per (app_id, user_id) pair
   - Prevent one app from exhausting resources
   - Different tiers for different apps

4. **Logging & Auditing**
   - Log all authentication attempts (success and failure)
   - Log authorization denials
   - Include `app_id`, `user_id` in all logs

5. **IP Allowlisting (Optional)**
   - Allow apps to configure IP ranges
   - Additional layer for server-to-server calls
   - Implement via container app firewall rules

## Testing Strategy

1. **Unit Tests**
   - Test API key verification
   - Test JWT verification with various payloads
   - Test authorization rules

2. **Integration Tests**
   - Test full auth flow (API key + JWT)
   - Test cross-tenant isolation
   - Test auth failures return correct status codes

3. **Load Tests**
   - Verify auth doesn't add significant latency
   - Test with high concurrency

## Next Steps

1. Decide on auth mode (recommend: `api_key_jwt` for MVP)
2. Design application registration process
3. Implement authentication middleware
4. Add database schema changes
5. Update API endpoints to use auth context
6. Write comprehensive tests
7. Document API authentication for consumers
