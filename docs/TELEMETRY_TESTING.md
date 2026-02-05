# Telemetry Testing Guide

This guide covers how to test the telemetry system locally and verify it's working correctly.

---

## Prerequisites

1. **Service running:**
   ```bash
   docker-compose up -d
   ```

2. **Service is healthy:**
   ```bash
   docker-compose ps
   # Should show "healthy" status
   ```

---

## Method 1: Quick Manual Test (No Azure Required)

### Step 1: Make some requests

```bash
# Health check
curl http://localhost:8765/health

# With session ID
curl -H "X-Session-ID: test-session-123" http://localhost:8765/health

# List configs
curl http://localhost:8765/api/v1/configs

# Trigger an error (404)
curl http://localhost:8765/api/v1/nonexistent
```

### Step 2: Check logs for telemetry

```bash
# View telemetry initialization
docker-compose logs amplifier-service | grep Telemetry

# You should see:
# [Telemetry] Application Insights initialized successfully
# OR
# [Telemetry] No Application Insights connection string found. Telemetry disabled.
```

### Step 3: Check dev logger output

```bash
# View all logs with telemetry context
docker-compose logs amplifier-service | tail -50

# Look for log entries with:
# - request_id
# - user_id
# - session_id
# - app_id
# - environment
```

### Step 4: Verify correlation IDs

```bash
# Each response should include X-Request-ID header
curl -v http://localhost:8765/health 2>&1 | grep X-Request-ID

# Output should show:
# < X-Request-ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

---

## Method 2: Automated Test Script

### Run the test script:

```bash
# From project root
python test_telemetry.py
```

### Expected output:

```
============================================================
Telemetry Testing Script
============================================================

[Test 1] Health Check
------------------------------------------------------------
✓ Status: 200
✓ Request ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
✓ Response: {'status': 'healthy', ...}

[Test 2] Health Check with Session ID
------------------------------------------------------------
✓ Status: 200
✓ Request ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
✓ Session ID passed: test-session-123

[Test 3] List Configs
------------------------------------------------------------
✓ Status: 200
✓ Request ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
✓ Configs found: 0

[Test 4] List Sessions
------------------------------------------------------------
✓ Status: 200
✓ Request ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
✓ Sessions found: 0

[Test 5] Error Handling (404)
------------------------------------------------------------
✓ Status: 404 (expected 404)
✓ Request ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

============================================================
✓ All tests completed successfully!
============================================================
```

---

## Method 3: Azure Application Insights (Full Integration Test)

### Prerequisites:

1. **Create Application Insights** (see README.md)
2. **Add connection string** to `.env`:
   ```bash
   TELEMETRY_APP_INSIGHTS_CONNECTION_STRING=InstrumentationKey=...
   ```
3. **Restart service:**
   ```bash
   docker-compose restart
   ```

### Step 1: Generate some traffic

```bash
# Run the automated test script
python test_telemetry.py

# Or make manual requests
for i in {1..10}; do
  curl http://localhost:8765/health
  sleep 1
done
```

### Step 2: Wait 2-5 minutes

Application Insights has a small ingestion delay.

### Step 3: Query in Azure Portal

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your Application Insights resource
3. Click **"Logs"** in the left menu
4. Run this query:

```kusto
// All telemetry events from your app
traces
| where timestamp > ago(30m)
| where customDimensions.app_id == "amplifier-app-api"
| project 
    timestamp, 
    message,
    request_id = customDimensions.request_id,
    user_id = customDimensions.user_id,
    session_id = customDimensions.session_id,
    environment = customDimensions.environment,
    endpoint = customDimensions.endpoint,
    method = customDimensions.method,
    status_code = customDimensions.status_code,
    duration_ms = customDimensions.duration_ms
| order by timestamp desc
```

### Step 4: Verify event properties

Every event should have:
- ✅ `request_id` - UUID correlation ID
- ✅ `user_id` - "anonymous" (if not authenticated)
- ✅ `session_id` - Session ID or null
- ✅ `app_id` - "amplifier-app-api"
- ✅ `environment` - "development" (or your configured value)

### Step 5: Check request metrics

```kusto
// Request count by endpoint
traces
| where timestamp > ago(1h)
| where message == "request_completed"
| summarize count() by tostring(customDimensions.endpoint)
| order by count_ desc
```

```kusto
// Request duration percentiles
traces
| where timestamp > ago(1h)
| where message == "request_completed"
| extend duration_ms = todouble(customDimensions.duration_ms)
| summarize 
    p50 = percentile(duration_ms, 50),
    p95 = percentile(duration_ms, 95),
    p99 = percentile(duration_ms, 99),
    max = max(duration_ms)
```

```kusto
// Error rate
traces
| where timestamp > ago(1h)
| where message in ("request_completed", "request_failed")
| summarize 
    total = count(),
    errors = countif(message == "request_failed")
| extend error_rate = (errors * 100.0) / total
```

---

## Method 4: Dev Logger Inspection (Local Testing)

### Step 1: Add a dev endpoint (optional)

You can add an endpoint to inspect the dev logger stats:

```python
# In amplifier_app_api/api/health.py

from ..telemetry import get_dev_logs, get_dev_log_stats

@router.get("/dev/telemetry/stats")
def get_telemetry_stats():
    """Get telemetry dev logger statistics (development only)."""
    return get_dev_log_stats()

@router.get("/dev/telemetry/logs")
def get_telemetry_logs():
    """Get recent telemetry events from dev logger (development only)."""
    logs = get_dev_logs()
    return {"events": logs[-50:]}  # Last 50 events
```

### Step 2: Query the endpoint

```bash
# Get stats
curl http://localhost:8765/dev/telemetry/stats

# Output:
{
  "event_count": 42,
  "size_bytes": 15234,
  "max_events": 1000,
  "max_size_bytes": 10485760,
  "debug_enabled": false
}

# Get recent events
curl http://localhost:8765/dev/telemetry/logs | jq '.events[-5:]'
```

---

## What to Look For

### ✅ Success Indicators

1. **Service starts without errors:**
   ```
   [Telemetry] Application Insights initialized successfully
   ```

2. **Every request has a correlation ID:**
   ```bash
   curl -v http://localhost:8765/health 2>&1 | grep X-Request-ID
   # Should return a UUID
   ```

3. **Logs include context:**
   ```
   # Logs should show structured data with:
   - request_id
   - user_id
   - session_id
   - app_id
   - environment
   ```

4. **Events appear in Azure (if configured):**
   - Check Azure Portal after 2-5 minutes
   - Query should return events with all required properties

### ❌ Failure Indicators

1. **Missing connection string (expected in dev):**
   ```
   [Telemetry] No Application Insights connection string found. Telemetry disabled.
   ```
   - This is OK locally - dev logger still works
   - Add connection string if you want Azure integration

2. **Import errors:**
   ```
   ModuleNotFoundError: No module named 'opencensus'
   ```
   - Run: `docker-compose build` to rebuild with dependencies

3. **Missing correlation ID:**
   ```bash
   curl -v http://localhost:8765/health 2>&1 | grep X-Request-ID
   # Returns nothing
   ```
   - Middleware might not be installed correctly

4. **No events in Azure (after 10+ minutes):**
   - Check connection string is correct
   - Verify telemetry is enabled: `TELEMETRY_ENABLED=true`
   - Check Azure quotas and ingestion status

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'opencensus'"

**Solution:**
```bash
# Rebuild the Docker image
docker-compose build --no-cache
docker-compose up -d
```

### Issue: "No Application Insights connection string found"

**Solution:**
This is expected if you haven't set up Azure yet. The dev logger still works.

To add Azure:
1. Create Application Insights in Azure Portal
2. Copy connection string
3. Add to `.env`:
   ```bash
   TELEMETRY_APP_INSIGHTS_CONNECTION_STRING=InstrumentationKey=...
   ```
4. Restart: `docker-compose restart`

### Issue: "Events not appearing in Azure"

**Checklist:**
1. Wait 5-10 minutes (ingestion delay)
2. Check connection string is correct
3. Verify service logs show "Application Insights initialized successfully"
4. Check Azure Portal → Application Insights → Failures (for ingestion errors)
5. Verify you're querying the correct time range (`ago(30m)`)

### Issue: "user_id or session_id is always null"

**Expected behavior:**
- `user_id` defaults to "anonymous" if not authenticated
- `session_id` is null unless:
  - Passed via `X-Session-ID` header
  - Set by auth middleware
  - Set in request state

**To test with session_id:**
```bash
curl -H "X-Session-ID: my-session-123" http://localhost:8765/health
```

---

## Performance Testing

### Test telemetry overhead:

```bash
# Install Apache Bench
apt-get install apache2-utils

# Baseline (without telemetry)
# Set TELEMETRY_ENABLED=false and restart
ab -n 1000 -c 10 http://localhost:8765/health

# With telemetry
# Set TELEMETRY_ENABLED=true and restart
ab -n 1000 -c 10 http://localhost:8765/health

# Compare mean request time
# Should be < 25ms overhead per the requirements
```

---

## Next Steps

After testing:

1. **Review events** in Azure Application Insights
2. **Set up alerts** for errors and performance
3. **Create dashboards** for key metrics
4. **Instrument business logic** (sessions, configs, tools)
5. **Add custom metrics** for business KPIs

See `docs/TELEMETRY_PLAN.md` for Phase 2 implementation details.
