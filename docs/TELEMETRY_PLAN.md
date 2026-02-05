# Service Telemetry Plan for amplifier-app-api

**Date:** 2026-02-05  
**Status:** Planning  
**Reference Implementation:** `amplifier-onboarding/lib/telemetry`

---

## Executive Summary

This document outlines the telemetry strategy for the amplifier-app-api service. Unlike the website telemetry system (which tracks user interactions and page views), service telemetry focuses on **operational health, request lifecycle, performance metrics, and business domain events**.

---

## Key Differences: Website vs Service Telemetry

### Website Telemetry (Reference Implementation)
- **User-centric**: Clicks, page views, user journeys
- **Frontend events**: UI interactions, form submissions, component lifecycle
- **Session-based**: Track user sessions across pages
- **Privacy-heavy**: PII concerns, GDPR consent management, DNT support
- **Client-side sampling**: Reduce load on user's browser
- **Universal click tracking**: Automatic capture of all interactions

### Service Telemetry (What We Need)
- **Request-centric**: API calls, endpoints, HTTP methods
- **Performance-focused**: Latency, throughput, resource utilization
- **Error tracking**: HTTP status codes, exceptions, validation failures
- **Operational**: Health checks, dependency status, quota monitoring
- **Server-side sampling**: Control costs and volume centrally
- **Structured logging**: Correlation IDs for distributed tracing

---

## Global Event Properties

**CRITICAL: Every telemetry event MUST include these properties:**

```python
{
    "user_id": "string",        # REQUIRED: User identifier (if authenticated, else "anonymous")
    "session_id": "string",     # REQUIRED: Session identifier (if in session context, else null)
    "app_id": "string",         # REQUIRED: Application identifier from config
    "environment": "string",    # REQUIRED: Environment (dev/staging/production) from .env
    "request_id": "string",     # REQUIRED: Correlation ID for request tracing
    "timestamp": "ISO8601",     # REQUIRED: Automatic (Application Insights adds this)
}
```

These are automatically injected via context propagation and telemetry initializers.

---

## Event Categories for amplifier-app-api

### 1. Request Lifecycle Events

Every API request should capture:

```python
# Core request events
- request_received
- request_completed
- request_failed

# Request-specific properties (in addition to global properties):
{
    "endpoint": "/api/v1/sessions",           # API endpoint path
    "method": "POST",                         # HTTP method
    "status_code": 200,                       # HTTP status code
    "duration_ms": 45,                        # Request duration
    "request_size_bytes": 1024,               # Request body size
    "response_size_bytes": 2048,              # Response body size
}
```

**When to track:**
- `request_received`: Middleware captures incoming request
- `request_completed`: Middleware captures successful response
- `request_failed`: Middleware captures exceptions/errors

---

### 2. Business Domain Events

#### Session Management
```python
# Session lifecycle
- session_created
  Properties: session_id, bundle_id, provider, initial_config_size
  
- session_resumed
  Properties: session_id, idle_duration_seconds, message_count
  
- session_message_sent
  Properties: session_id, message_length, has_attachments
  
- session_message_received
  Properties: session_id, response_length, provider_latency_ms
  
- session_deleted
  Properties: session_id, session_age_seconds, message_count
  
- session_expired
  Properties: session_id, reason, last_activity_timestamp
```

#### Configuration Management
```python
# Config lifecycle
- config_created
  Properties: config_id, bundle_count, provider_count, tool_count
  
- config_updated
  Properties: config_id, fields_changed, validation_duration_ms
  
- config_deleted
  Properties: config_id, config_age_seconds, session_count
  
- config_validated
  Properties: config_id, validation_duration_ms, warnings_count
  
- config_validation_failed
  Properties: config_id, error_type, error_field, validation_duration_ms
```

#### Tool Invocations
```python
# Tool execution
- tool_invoked
  Properties: tool_name, input_size_bytes
  
- tool_execution_started
  Properties: tool_name, parameters_hash
  
- tool_execution_completed
  Properties: tool_name, duration_ms, output_size_bytes
  
- tool_execution_failed
  Properties: tool_name, error_type, duration_ms
```

#### Bundle Operations
```python
# Bundle lifecycle
- bundle_loaded
  Properties: bundle_name, bundle_version, load_duration_ms
  
- bundle_validated
  Properties: bundle_name, validation_duration_ms, has_errors
  
- bundle_validation_failed
  Properties: bundle_name, error_type, error_message
```

#### Health and Monitoring
```python
# Health checks
- health_check_requested
  Properties: check_type
  
- health_check_completed
  Properties: check_type, status, duration_ms, details
  
- health_check_failed
  Properties: check_type, error_type, error_message

# Smoke tests
- smoke_test_started
  Properties: test_suite, test_count
  
- smoke_test_completed
  Properties: test_suite, passed_count, failed_count, duration_ms
  
- smoke_test_failed
  Properties: test_suite, test_name, error_type, error_message
```

**Note on Timestamps:** Yes, all events automatically include timestamps. Application Insights adds an ISO8601 timestamp to every event automatically.

---

### 3. Performance Metrics

Track these as **metrics** (numeric values over time), not just events:

```python
# Request metrics
- request_duration_ms          # Histogram: Distribution of request times
- requests_per_second          # Counter: Total request rate
- requests_by_endpoint         # Counter: Requests per endpoint
- requests_by_status_code      # Counter: 2xx, 4xx, 5xx counts

# Resource metrics
- active_sessions_count        # Gauge: Current active sessions
- active_configs_count         # Gauge: Current active configs
- database_connection_pool     # Gauge: DB connections (used/available)
- memory_usage_mb              # Gauge: Process memory consumption
- cpu_usage_percent            # Gauge: Process CPU usage

# Business metrics
- sessions_created_count       # Counter: Total sessions created
- configs_created_count        # Counter: Total configs created
- tools_invoked_count          # Counter: Total tool invocations
- cache_hit_rate              # Gauge: Config cache hit percentage

# Database metrics
- database_query_duration_ms   # Histogram: Query performance
- database_queries_count       # Counter: Total queries
- database_connection_errors   # Counter: Connection failures
```

---

### 4. Error Events

Structured error tracking with categorization:

```python
# Error categories
- validation_error
  Properties: field_name, validation_rule, input_value_hash
  
- authentication_error
  Properties: auth_method, failure_reason
  
- authorization_error
  Properties: required_permission, user_role
  
- database_error
  Properties: operation, table_name, error_code, is_retryable
  
- external_service_error
  Properties: service_name, endpoint, status_code, retry_count
  
- timeout_error
  Properties: operation, timeout_threshold_ms, actual_duration_ms
  
- rate_limit_exceeded
  Properties: limit_type, current_count, limit_threshold, window_seconds

# Standard error properties:
{
    "error_type": "ValidationError",
    "error_message": "Invalid bundle configuration",
    "error_code": "CONFIG_001",
    "stack_trace": "sanitized stack trace",
    "endpoint": "/api/v1/configs",
    "request_id": "uuid",
    "is_retryable": false,
}
```

---

### 5. Dependency Health Events

Track external dependencies and their health:

```python
# Database
- database_connection_acquired
  Properties: pool_size, wait_time_ms
  
- database_connection_released
  Properties: connection_duration_ms, queries_executed
  
- database_connection_failed
  Properties: error_type, retry_count, backoff_ms

# External APIs (if any)
- external_api_called
  Properties: service_name, endpoint, method
  
- external_api_succeeded
  Properties: service_name, duration_ms, status_code
  
- external_api_failed
  Properties: service_name, error_type, retry_attempt

# Cache (if implemented)
- cache_miss
  Properties: cache_key_hash, lookup_duration_ms
  
- cache_hit
  Properties: cache_key_hash, lookup_duration_ms, entry_age_seconds
  
- cache_eviction
  Properties: eviction_reason, entries_evicted
```

---

### 6. Security Events

Important for audit trails and security monitoring:

```python
# Authentication
- authentication_attempted
  Properties: auth_method, source_ip_hash
  
- authentication_succeeded
  Properties: user_id, auth_method, session_created
  
- authentication_failed
  Properties: auth_method, failure_reason, attempts_count

# Authorization
- api_key_validated
  Properties: api_key_id, scope, permissions
  
- api_key_rejected
  Properties: api_key_id_prefix, rejection_reason
  
- permission_denied
  Properties: required_permission, user_permissions, resource

# Rate limiting
- rate_limit_triggered
  Properties: limit_type, user_id, window_seconds, request_count
  
- rate_limit_warning
  Properties: limit_type, usage_percent, threshold_percent

# Suspicious activity
- suspicious_activity_detected
  Properties: activity_type, risk_score, indicators
```

---

## Proposed Architecture

### Directory Structure

```
amplifier_app_api/
├── telemetry/
│   ├── __init__.py           # Public API exports
│   ├── tracker.py            # Core ApplicationInsights wrapper
│   ├── middleware.py         # FastAPI middleware for request tracking
│   ├── events.py             # Event name constants (like eventNaming.ts)
│   ├── metrics.py            # Metric definitions and tracking
│   ├── context.py            # Request context and correlation IDs
│   ├── config.py             # Telemetry configuration
│   └── sanitizer.py          # PII sanitization utilities
```

### Key Components

#### 1. Middleware for Automatic Request Tracking

**Purpose:** Capture every API request automatically without manual instrumentation

**Features:**
- Measure request duration
- Track status codes
- Capture exceptions
- Generate correlation IDs
- Inject context into request lifecycle
- Sample requests based on config

**Example:**
```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time

class TelemetryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_id = generate_correlation_id()
        
        # Store in request state for downstream access
        request.state.request_id = request_id
        request.state.start_time = start_time
        
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            
            track_event("request_completed", {
                "endpoint": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "request_id": request_id,
            })
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            track_exception(e, {
                "endpoint": request.url.path,
                "method": request.method,
                "duration_ms": duration_ms,
                "request_id": request_id,
            })
            raise
```

#### 2. Context Propagation with Correlation IDs

**Purpose:** Trace requests through the entire system

**Flow:**
```
API Endpoint (request_id generated)
    ↓ (pass request_id)
Session Manager (uses same request_id)
    ↓ (pass request_id)
Database Layer (logs with request_id)
    ↓ (pass request_id)
External Services (include in headers)
```

**Implementation:**
```python
from contextvars import ContextVar

# Thread-safe request context
request_context: ContextVar[dict] = ContextVar('request_context', default={})

def set_request_context(request_id: str, **kwargs):
    request_context.set({
        "request_id": request_id,
        **kwargs
    })

def get_request_context() -> dict:
    return request_context.get()

# All telemetry events automatically include request_id
def track_event(name: str, properties: dict):
    context = get_request_context()
    merged_properties = {**context, **properties}
    app_insights.track_event(name, merged_properties)
```

#### 3. Structured Event System

**Purpose:** Type-safe, validated event tracking

**Pattern from website reference:**
```python
# events.py - Centralized event names
class TelemetryEvents:
    # Request lifecycle
    REQUEST_RECEIVED = "request_received"
    REQUEST_COMPLETED = "request_completed"
    REQUEST_FAILED = "request_failed"
    
    # Session domain
    SESSION_CREATED = "session_created"
    SESSION_RESUMED = "session_resumed"
    SESSION_DELETED = "session_deleted"
    
    # Config domain
    CONFIG_CREATED = "config_created"
    CONFIG_UPDATED = "config_updated"
    CONFIG_VALIDATED = "config_validated"
    
    # ... etc
```

---

## What to Adapt from Website Reference

### ✅ Keep These Patterns

1. **Event Naming Convention**
   - `{domain}_{entity}_{action}` pattern works well
   - Example: `session_message_sent`, `config_validation_failed`

2. **Structured Event Properties**
   - Type-safe event definitions using TypeScript/Python dataclasses
   - Validation of event properties before sending

3. **Development Logger**
   - JSONL export for local debugging is brilliant
   - Export logs for local analysis
   - Console tools for debugging

4. **Configuration System**
   - Centralized telemetry config
   - Environment-specific settings
   - Easy toggle for dev/staging/production

5. **Sanitization Utilities**
   - Still need to sanitize PII in API requests
   - Hash sensitive values (IP addresses, user IDs)
   - Truncate large payloads

6. **Singleton Pattern with Lazy Initialization**
   - Initialize telemetry once at app startup
   - Provide getter for the instance
   - Handle case where telemetry is disabled

### ❌ Don't Need from Website Reference

1. **Click Tracking**
   - Not applicable to APIs

2. **Page View Tracking**
   - No pages in an API service

3. **User Identity with localStorage**
   - Use API keys/auth tokens instead
   - Track authenticated users via headers

4. **Consent Management**
   - Different compliance model for B2B APIs
   - Server-side data, not user browser data

5. **Client-side Sampling**
   - Do server-side sampling instead
   - More control over costs

6. **React Hooks**
   - No component lifecycle in services

---

## Configuration Design

### Environment-Specific Settings

```python
# config.py
from pydantic import BaseSettings

class TelemetryConfig(BaseSettings):
    # Connection
    app_insights_connection_string: str | None = None
    enabled: bool = True
    
    # Sampling
    sample_rate: float = 1.0  # 1.0 = 100%, 0.1 = 10%
    sample_rate_errors: float = 1.0  # Always capture errors
    
    # Privacy
    sanitize_pii: bool = True
    hash_ip_addresses: bool = True
    truncate_large_payloads: bool = True
    max_payload_size: int = 10_000  # characters
    
    # Performance
    batch_size: int = 10
    flush_interval_seconds: int = 5
    
    # Development
    enable_dev_logger: bool = True
    dev_logger_max_size_mb: int = 10
    
    # Request tracking
    track_request_headers: bool = False
    track_response_headers: bool = False
    track_request_body: bool = False  # Privacy risk
    track_response_body: bool = False  # Privacy risk
    
    class Config:
        env_prefix = "TELEMETRY_"
        env_file = ".env"
```

### Usage

```bash
# .env file
TELEMETRY_ENABLED=true
TELEMETRY_APP_INSIGHTS_CONNECTION_STRING=InstrumentationKey=...
TELEMETRY_SAMPLE_RATE=0.1  # Sample 10% of requests in production
TELEMETRY_ENABLE_DEV_LOGGER=true
```

---

## Implementation Priority

### Phase 1: Foundation (Week 1)
- [ ] Set up basic ApplicationInsights integration
- [ ] Create telemetry middleware for request tracking
- [ ] Implement correlation ID context propagation
- [ ] Add development logger (JSONL export)
- [ ] Define core event names

### Phase 2: Domain Events (Week 2)
- [ ] Instrument session lifecycle events
- [ ] Instrument config lifecycle events
- [ ] Add error categorization
- [ ] Implement PII sanitization

### Phase 3: Metrics (Week 3)
- [ ] Add performance metrics (latency, throughput)
- [ ] Add resource metrics (memory, connections)
- [ ] Add business metrics (sessions, configs, tools)
- [ ] Set up metric dashboards in Azure

### Phase 4: Advanced (Week 4)
- [ ] Implement smart sampling (sample errors more than success)
- [ ] Add security event tracking
- [ ] Set up alerting rules
- [ ] Document telemetry for team

---

## Open Questions for Discussion

1. **Connection String Management**
   - Should we use separate App Insights instances for dev/staging/prod? [FEEDBACK] No we don't need separate instances. Instead add environment to all telemetry events, and we will configure that in the .env file.
   - How do we handle connection string rotation? [FEEDBACK] Do we need to worry about this right now?

2. **PII and Privacy**
   - What fields need sanitization? (user IDs, IP addresses, config content?) [FEEDBACK] user_id
   - Do we need to support data deletion requests (GDPR)? [FEEDBACK] no not right now.

3. **Sampling Strategy**
   - What sample rate for production? (10%? 50%? 100%?) [FEEDBACK] 100% for now
   - Should we always capture errors regardless of sample rate? [FEEDBACK] yes
   - Should we sample more aggressively for certain endpoints? [FEEDBACK] no

4. **Performance Impact**
   - What's acceptable overhead? (<5ms per request?) [FEEDBACK] <25ms per request
   - Should we batch events or send immediately? [FEEDBACK] Follow whatever the amplifier-onboarding solution does.

5. **Alerting Rules**
   - What conditions should trigger alerts? [FEEDBACK] I'll deal with those on the app insights side.
   - Who receives alerts? (email, Slack, PagerDuty?) [FEEDBACK] Again, I'll deal with those on the azure app insights side.

6. **Retention and Costs**
   - How long should we retain telemetry data? [FEEDBACK] Again I'll deal with that on the azure app insights side.
   - What's the expected monthly cost? [FEEDBACK]n/a

---

## Next Steps

Please review this plan and provide feedback on:

1. **Event Categories**: Are these the right events to track?
2. **Architecture**: Does the proposed structure make sense?
3. **Configuration**: Any settings we're missing?
4. **Implementation Priority**: Does the phasing make sense?
5. **Open Questions**: Answers to the questions above

Once we have alignment, I can:
- Implement the telemetry module
- Add middleware to FastAPI app
- Instrument existing endpoints
- Create example queries and dashboards

---

## References

- **Website Telemetry**: `amplifier-onboarding/lib/telemetry`
- **FastAPI Service**: `amplifier-app-api`
- **Azure App Insights Docs**: https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview
- **OpenTelemetry**: https://opentelemetry.io/ (future consideration)
