# Telemetry System

**Last Updated:** 2026-01-11
**Status:** Production
**Components:** config_service, telemetry_collector, web_ui, vendor_service

## Overview

IncidentFox includes an optional telemetry system that collects anonymous usage metrics to help improve the product. Organizations can opt-in or opt-out at any time through the web UI. All telemetry data is aggregated, anonymized, and sent to a vendor service for analysis.

## Architecture

```
┌─────────────────┐
│   Web UI        │  User toggles telemetry on/off
│   (Settings)    │
└────────┬────────┘
         │ PUT /api/config/me/org-settings
         ▼
┌─────────────────┐
│ Config Service  │  Stores org_settings.telemetry_enabled
│ (FastAPI)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐       ┌──────────────────┐
│   PostgreSQL    │◄──────┤ Telemetry        │
│   Database      │       │ Collector        │
│                 │       │ (Sidecar)        │
└─────────────────┘       └────────┬─────────┘
                                   │
                                   │ Heartbeat (5min)
                                   │ Analytics (daily 2AM UTC)
                                   ▼
                          ┌──────────────────┐
                          │ Vendor Service   │
                          │ (AWS Lambda)     │
                          └──────────────────┘
```

## Components

### 1. Config Service (`config_service/`)

**New Database Schema:**
- **Table:** `org_settings`
  - `org_id` (VARCHAR(64), PK) - Organization identifier
  - `telemetry_enabled` (BOOLEAN, default TRUE) - Opt-in/out flag
  - `created_at` (TIMESTAMP) - Record creation time
  - `updated_at` (TIMESTAMP) - Last update time
  - `updated_by` (VARCHAR(128)) - User who last updated

**New API Endpoints:**

#### GET `/api/v1/config/me/org-settings`
Get current telemetry preference for the authenticated team's organization.

**Authentication:** Team token (same as other /me endpoints)

**Response:**
```json
{
  "org_id": "extend",
  "telemetry_enabled": true,
  "updated_at": "2026-01-11T19:05:21.133463Z",
  "updated_by": "team_abc123"
}
```

#### PUT `/api/v1/config/me/org-settings`
Update telemetry preference for the authenticated team's organization.

**Authentication:** Team token

**Request Body:**
```json
{
  "telemetry_enabled": false
}
```

**Response:**
```json
{
  "org_id": "extend",
  "telemetry_enabled": false,
  "updated_at": "2026-01-11T19:10:30.456789Z",
  "updated_by": "team_abc123"
}
```

**Migration:**
```bash
# Migration: 20260111_0001_org_settings.py
alembic upgrade head
```

### 2. Telemetry Collector (`telemetry_collector/`)

A standalone sidecar service that:
1. **Validates license** with vendor service on startup
2. **Collects metrics** from the config service database every 5 minutes (heartbeat)
3. **Aggregates analytics** daily at 2:00 AM UTC
4. **Respects opt-out** by filtering queries with `LEFT JOIN org_settings`

**Query Pattern:**
All telemetry queries exclude opted-out organizations:
```sql
SELECT COUNT(*)
FROM agent_runs ar
LEFT JOIN org_settings os ON ar.org_id = os.org_id
WHERE (os.telemetry_enabled IS NULL OR os.telemetry_enabled = TRUE)
  AND DATE(ar.started_at) = :today
```

**Key Features:**
- **NULL-safe filtering:** Organizations without explicit settings default to enabled
- **Immediate opt-out:** Changes take effect on next query (within 5 minutes)
- **License caching:** 1-hour TTL to minimize vendor API calls
- **Health endpoint:** `/health` for Kubernetes liveness/readiness probes

**Environment Variables:**
```bash
DATABASE_URL=postgresql://...              # Config service database
VENDOR_SERVICE_URL=https://...             # Vendor service endpoint
VENDOR_LICENSE_KEY=xxx                     # Organization license key
HEARTBEAT_INTERVAL_SECONDS=300             # 5 minutes
ANALYTICS_HOUR_UTC=2                       # 2 AM UTC
LICENSE_CACHE_TTL_SECONDS=3600             # 1 hour
```

**Kubernetes Deployment:**
```bash
kubectl apply -f telemetry_collector/k8s/config.yaml
kubectl apply -f telemetry_collector/k8s/deployment.yaml
```

### 3. Web UI (`web_ui/`)

**Settings Page:** `/settings`

New "Telemetry" tab with three sections:

1. **What data is collected?**
   - Agent run metrics (counts, success/failure rates, duration, timeouts)
   - Usage patterns (tool usage, agent types, trigger sources)
   - Performance statistics (avg duration, p50/p95/p99, error types)
   - Team activity (active teams, total teams)

2. **What is NOT collected?**
   - Personal information, credentials, or tokens
   - Agent prompts, messages, or conversation content
   - Knowledge base documents or team-specific data
   - API keys, secrets, or integration credentials
   - IP addresses, hostnames, or network identifiers

3. **How is data used?**
   - Aggregated and anonymized for product improvement
   - Sent securely to vendor service
   - Never shared with third parties
   - Reporting frequency: 5min heartbeat + daily 2AM UTC

**Toggle Component:**
```tsx
// Load current setting
const res = await apiFetch('/api/config/me/org-settings');
const data = await res.json();
setTelemetryEnabled(data.telemetry_enabled);

// Update setting
await apiFetch('/api/config/me/org-settings', {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ telemetry_enabled: newValue }),
});
```

### 4. Vendor Service

See `incidentfox-vendor-service` repository for details.

**Endpoints:**
- `POST /validate-license` - License validation
- `POST /telemetry/heartbeat` - 5-minute metrics
- `POST /telemetry/analytics` - Daily aggregated data

## Data Collected

### Heartbeat Metrics (Every 5 Minutes)

```json
{
  "customer_id": "extend",
  "timestamp": "2026-01-11T19:05:21.133463Z",
  "metrics": {
    "runs_today": 42,
    "runs_last_hour": 8,
    "successful_runs_today": 38,
    "failed_runs_today": 4,
    "avg_duration_seconds": 45.3,
    "total_teams": 5,
    "active_teams_today": 3
  }
}
```

### Daily Analytics (2:00 AM UTC)

```json
{
  "customer_id": "extend",
  "date": "2026-01-11",
  "analytics": {
    "total_runs": 150,
    "successful_runs": 142,
    "failed_runs": 6,
    "timeout_runs": 2,
    "avg_duration_seconds": 42.5,
    "p50_duration_seconds": 35.0,
    "p95_duration_seconds": 85.2,
    "p99_duration_seconds": 120.5,
    "avg_tool_calls": 8.3,
    "total_teams": 5,
    "active_teams": 3,
    "runs_by_trigger": {
      "webhook": 80,
      "manual": 45,
      "scheduled": 25
    },
    "runs_by_agent": {
      "planner": 90,
      "k8s": 35,
      "investigation": 25
    },
    "top_errors": [
      {"error_type": "timeout", "count": 2},
      {"error_type": "tool_error", "count": 4}
    ]
  }
}
```

## Privacy & Security

### What We Collect
- Aggregate metrics (counts, averages, percentiles)
- Error types and frequency
- Tool/agent usage patterns
- Performance statistics

### What We DON'T Collect
- Personal information (names, emails, IPs)
- Credentials or API keys
- Agent prompts or conversation content
- Knowledge base documents
- Team-specific or customer-specific data
- Network identifiers

### Security Measures
- **TLS encryption** for all vendor service communication
- **License key authentication** (not customer data)
- **Aggregation only** - no individual run details sent
- **Immediate opt-out** - changes take effect within 5 minutes
- **Stateless collector** - no local data storage

## Operations

### Enable/Disable Telemetry

**Via Web UI:**
1. Navigate to Settings → Telemetry
2. Toggle the switch on/off
3. Changes take effect immediately (within 5 minutes)

**Via API:**
```bash
# Disable telemetry
curl -X PUT https://ui.incidentfox.ai/api/config/me/org-settings \
  -H "Authorization: Bearer $TEAM_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"telemetry_enabled": false}'

# Enable telemetry
curl -X PUT https://ui.incidentfox.ai/api/config/me/org-settings \
  -H "Authorization: Bearer $TEAM_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"telemetry_enabled": true}'
```

**Via Database (Emergency):**
```sql
-- Disable for specific org
INSERT INTO org_settings (org_id, telemetry_enabled)
VALUES ('extend', false)
ON CONFLICT (org_id) DO UPDATE SET telemetry_enabled = false;

-- Enable for specific org
UPDATE org_settings SET telemetry_enabled = true WHERE org_id = 'extend';

-- Check current status
SELECT org_id, telemetry_enabled, updated_at FROM org_settings;
```

### Monitoring

**Telemetry Collector Health:**
```bash
# Check pod status
kubectl get pods -n incidentfox -l app=telemetry-collector

# Check logs
kubectl logs -n incidentfox deployment/telemetry-collector --tail=100

# Check health endpoint
kubectl exec -n incidentfox deployment/telemetry-collector -- \
  curl -s http://localhost:8000/health
```

**Expected Logs:**
```json
{"service": "telemetry_collector", "event": "license_validated_startup", "customer": "Acme Corp"}
{"service": "telemetry_collector", "event": "telemetry_collector_started"}
{"service": "telemetry_collector", "event": "analytics_scheduled", "next_run": "2026-01-12T02:00:00+00:00"}
{"service": "telemetry_collector", "event": "heartbeat_sent", "runs_today": 42}
```

**Metrics to Monitor:**
- Telemetry collector pod restarts
- Failed heartbeat/analytics sends
- Database connection errors
- Vendor service HTTP errors

### Troubleshooting

**Issue:** Telemetry toggle not working
- Check config_service logs for API errors
- Verify org_settings table exists: `SELECT * FROM org_settings;`
- Confirm API endpoint responds: `curl -H "Authorization: Bearer $TOKEN" https://ui.incidentfox.ai/api/config/me/org-settings`

**Issue:** Telemetry still sending after opt-out
- Check telemetry_collector logs for query filters
- Verify database has opt-out: `SELECT * FROM org_settings WHERE org_id = 'extend';`
- Wait up to 5 minutes for next heartbeat cycle

**Issue:** License validation failing
- Check vendor service URL: `echo $VENDOR_SERVICE_URL`
- Check license key: `echo $VENDOR_LICENSE_KEY | cut -c1-10`
- Test vendor service manually: `curl -X POST $VENDOR_SERVICE_URL/validate-license ...`

## Development

### Running Locally

```bash
# 1. Set up database with org_settings table
cd config_service
alembic upgrade head

# 2. Start telemetry collector
cd telemetry_collector
export DATABASE_URL="postgresql://..."
export VENDOR_SERVICE_URL="https://..."
export VENDOR_LICENSE_KEY="..."
python -m src.telemetry_collector.api_server

# 3. Test API endpoints
curl http://localhost:8000/health
```

### Testing Opt-Out

```bash
# 1. Create test data
psql $DATABASE_URL -c "INSERT INTO agent_runs (org_id, ...) VALUES ('test-org', ...);"

# 2. Opt out
psql $DATABASE_URL -c "INSERT INTO org_settings (org_id, telemetry_enabled) VALUES ('test-org', false);"

# 3. Verify queries exclude opted-out org
# Check telemetry_collector logs - should not include test-org data
```

### Database Schema Evolution

When adding new telemetry metrics:

1. **Update queries** in `telemetry_collector/src/telemetry_collector/{heartbeat,analytics}.py`
2. **Maintain opt-out filter**: Always use `LEFT JOIN org_settings ... WHERE (os.telemetry_enabled IS NULL OR os.telemetry_enabled = TRUE)`
3. **Test with opted-out org** to ensure data is excluded
4. **Update documentation** in this file and `telemetry_collector/README.md`

## Migration Guide

### From No Telemetry to Telemetry System

1. **Deploy config_service with migration:**
   ```bash
   kubectl exec -n incidentfox deployment/incidentfox-config-service -- \
     python3 -m alembic upgrade head
   ```

2. **Deploy telemetry_collector:**
   ```bash
   kubectl apply -f telemetry_collector/k8s/config.yaml
   kubectl apply -f telemetry_collector/k8s/deployment.yaml
   ```

3. **Deploy updated web_ui:**
   ```bash
   docker build -t incidentfox-web-ui:latest web_ui/
   kubectl rollout restart deployment/incidentfox-web-ui -n incidentfox
   ```

4. **Verify:**
   - Check org_settings table exists
   - Confirm telemetry_collector pod is running
   - Test Settings → Telemetry toggle in UI

### Rolling Back

1. **Disable telemetry for all orgs:**
   ```sql
   UPDATE org_settings SET telemetry_enabled = false;
   ```

2. **Stop telemetry_collector:**
   ```bash
   kubectl scale deployment/telemetry-collector -n incidentfox --replicas=0
   ```

3. **Optionally remove components:**
   ```bash
   kubectl delete deployment/telemetry-collector -n incidentfox
   kubectl delete service/telemetry-collector -n incidentfox
   ```

## Related Documentation

- [config_service/README.md](../config_service/README.md) - Config service API details
- [telemetry_collector/README.md](../telemetry_collector/README.md) - Collector implementation
- [web_ui/README.md](../web_ui/README.md) - UI components
- [ARCHITECTURE_DECISIONS.md](./ARCHITECTURE_DECISIONS.md) - System architecture
- Vendor service: `incidentfox-vendor-service` repository

## Change Log

### 2026-01-11
- Initial telemetry system implementation
- Added org_settings table to config_service
- Implemented telemetry_collector sidecar service
- Added Telemetry tab to Settings page
- Deployed to production EKS cluster
