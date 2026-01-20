# Agent Service - External Integrations

This document details how to configure external integrations used by agent tools.

---

## GitHub App

The GitHub App integration enables the agent to interact with GitHub repositories.

### Configuration

```bash
# Kubernetes Secret: incidentfox-github
GITHUB_APP_ID=1234567
GITHUB_INSTALLATION_ID=12345678
GITHUB_PRIVATE_KEY_B64=<base64-encoded-private-key>
GITHUB_WEBHOOK_SECRET=<webhook-secret>
```

**Webhook URL** (points to Orchestrator):
```
https://orchestrator.incidentfox.ai/webhooks/github
```

### Available Tools

- `search_github_code` - Search code across repositories
- `read_github_file` - Read file contents
- `create_pull_request` - Create PRs
- `list_pull_requests` - List PRs
- `merge_pull_request` - Merge PRs
- `create_issue` - Create issues
- `list_issues` - List issues
- `close_issue` - Close issues
- `create_branch` - Create branches
- `list_branches` - List branches
- `list_files` - List repository files
- `get_repo_info` - Get repository metadata
- `trigger_workflow` - Trigger GitHub Actions
- `list_workflow_runs` - List workflow runs

See: `agent/src/ai_agent/tools/github_tools.py`

---

## Coralogix

Log management and observability platform integration.

### Configuration

```bash
# Kubernetes Secret: incidentfox-coralogix
CORALOGIX_API_KEY=cxup_xxxxxxxxxxxxxxxxxxxxxxxxxxxx  # Personal Key (NOT Send-Your-Data key!)
CORALOGIX_DOMAIN=your-domain.coralogix.com
```

**API Base URL**:
```
https://ng-api-http.cx498.coralogix.com
```

### DataPrime Query Example

```bash
curl -X POST "https://ng-api-http.cx498.coralogix.com/api/v1/dataprime/query" \
  -H "Authorization: Bearer $CORALOGIX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "source logs | limit 5",
    "metadata": {
      "startDate": "2026-01-08T10:00:00Z",
      "endDate": "2026-01-08T20:00:00Z",
      "tier": "TIER_FREQUENT_SEARCH"
    }
  }'
```

### Severity Levels

Numeric strings:
- `1` = Debug
- `2` = Verbose
- `3` = Info
- `4` = Warning
- `5` = Error
- `6` = Critical

### DataPrime Field Access

- Labels: `$l.applicationname`, `$l.subsystemname`
- Metadata: `$m.severity`, `$m.timestamp`
- User Data: `$d.logRecord.body`

### Available Tools

- `search_coralogix_logs` - Query logs using DataPrime
- `get_coralogix_error_logs` - Get recent errors
- `get_coralogix_alerts` - Get active alerts
- `query_coralogix_metrics` - Query metrics
- `search_coralogix_traces` - Search traces
- `get_coralogix_service_health` - Get service health
- `list_coralogix_services` - List all services

See: `agent/src/ai_agent/tools/coralogix_tools.py`

### Important Notes

- Use **Personal Key** (`cxup_*`) with query permissions
- Do NOT use Send-Your-Data keys (`cxtp_*`) - they lack query permissions

---

## Snowflake

Data warehouse integration for incident enrichment data.

### Configuration

```bash
# Kubernetes Secret: incidentfox-snowflake
SNOWFLAKE_ACCOUNT=your-account.region
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_WAREHOUSE=YOUR_WAREHOUSE
SNOWFLAKE_DATABASE=YOUR_DATABASE
SNOWFLAKE_SCHEMA=YOUR_SCHEMA
```

### Available Tables

| Table | Description | Key Columns |
|-------|-------------|-------------|
| `fact_incident` | Incidents | INCIDENT_ID, SEV, TITLE, STARTED_AT, RESOLVED_AT, ROOT_CAUSE_TYPE, STATUS |
| `fact_incident_customer_impact` | Customer impact | CUSTOMER_ID, ESTIMATED_ARR_AT_RISK_USD, IMPACTED_REQUESTS |
| `dim_customer` | Customers | CUSTOMER_NAME, TIER, ARR_USD, CUSTOMER_REGION |
| `fact_deployment` | Deployments | COMMIT_SHA, AUTHOR, SERVICE_NAME |
| `dim_service` | Services | Service metadata |

### Available Tools

- `get_recent_incidents` - Query recent incidents
- `get_incident_customer_impact` - Get customer impact for incident
- `get_deployment_incidents` - Find incidents related to deployments
- `get_customer_info` - Get customer details
- `get_incident_timeline` - Get incident timeline
- `search_incidents_by_service` - Find incidents by service
- `get_snowflake_schema` - Get table schema
- `run_snowflake_query` - Execute custom SQL

See: `agent/src/ai_agent/tools/snowflake_tools.py`

---

## Slack

Slack integration for notifications and interactions.

### Configuration

```bash
# Kubernetes Secret: incidentfox-slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
```

### Channel Routing

Slack channels are mapped to teams via the routing configuration in Config Service.

Example:
- Channel `C0A4967KRBM` → `extend-sre` team

See: `/docs/ROUTING_DESIGN.md` and `/orchestrator/docs/WEBHOOKS.md`

### Available Tools

- `search_slack_messages` - Search message history
- `get_channel_history` - Get channel messages
- `get_thread_replies` - Get thread replies
- `post_slack_message` - Send messages

See: `agent/src/ai_agent/tools/slack_tools.py`

---

## Testing Integrations Locally

### Test Snowflake

```python
import os
os.environ['SNOWFLAKE_ACCOUNT'] = 'your-account.region'
os.environ['SNOWFLAKE_USER'] = 'your_username'
os.environ['SNOWFLAKE_PASSWORD'] = 'your_password'
os.environ['SNOWFLAKE_WAREHOUSE'] = 'YOUR_WAREHOUSE'
os.environ['SNOWFLAKE_DATABASE'] = 'YOUR_DATABASE'
os.environ['SNOWFLAKE_SCHEMA'] = 'YOUR_SCHEMA'

from ai_agent.tools.snowflake_tools import get_recent_incidents
print(get_recent_incidents(limit=3))
```

### Test Coralogix

```python
import os
os.environ['CORALOGIX_API_KEY'] = 'cxup_xxxxxxxxxxxxxxxxxxxxxxxxxxxx'
os.environ['CORALOGIX_DOMAIN'] = 'your-domain.coralogix.com'

from ai_agent.tools.coralogix_tools import search_coralogix_logs
print(search_coralogix_logs(query='source logs | limit 3', time_range_minutes=60))
```

### Test in Pod

```bash
# Test Coralogix in pod
kubectl exec -n incidentfox deploy/incidentfox-agent -- python -c "
from ai_agent.tools.coralogix_tools import search_coralogix_logs
import json
result = search_coralogix_logs(query='source logs | limit 3', time_range_minutes=60)
print(json.loads(result)['success'])
"

# Test Snowflake in pod
kubectl exec -n incidentfox deploy/incidentfox-agent -- python -c "
from ai_agent.tools.snowflake_tools import get_recent_incidents
import json
result = get_recent_incidents(limit=2)
print(json.loads(result)['success'])
"
```

---

## Adding New Integrations

1. Create new tool file: `agent/src/ai_agent/tools/<integration>_tools.py`
2. Implement tools using the execution context pattern (see existing tools)
3. Add library check to `agent/src/ai_agent/tools/tool_loader.py`
4. Add Kubernetes secret with credentials
5. Add integration schema to Config Service
6. Document in this file

See: `agent/docs/TOOLS_CATALOG.md` for tool development guide.
