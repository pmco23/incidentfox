# Slack Investigation Flow (Starship)

**Real-time incident investigation with progressive updates in Slack.**

## Overview

When an incident is triggered in Slack, IncidentFox provides a rich, interactive investigation experience:

```
┌─────────────────────────────────────────────────────────────────────┐
│ 🦊 IncidentFox Investigation                                         │
│ Incident: INC-2024-0456 | Severity: 🔴 Critical                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│ *Investigation Progress:*                                            │
│                                                                       │
│ ✅ Snowflake: Historical incident patterns         [View]           │
│ ✅ Coralogix: Error logs & traces                  [View]           │
│ ⏳ Kubernetes: Pod health & events                                   │
│ ⏳ Root cause analysis                                               │
│                                                                       │
├─────────────────────────────────────────────────────────────────────┤
│ *Preliminary Findings:*                                              │
│                                                                       │
│ 🎯 Likely cause: Payment gateway timeout                            │
│    • First seen: 14:23:45 UTC                                        │
│    • Affected services: checkout, cart, payments                    │
│    • Error rate: 45% (normally <1%)                                  │
│                                                                       │
├─────────────────────────────────────────────────────────────────────┤
│ [🔧 View Remediation Options]  [📋 Full Report]                     │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Investigation Phases

The investigation runs through multiple phases, each handled by a specialized component:

| Phase | Purpose | Tools Used |
|-------|---------|------------|
| **Historical Analysis** | Check for similar past incidents | Snowflake, Knowledge Base |
| **Log Analysis** | Find error patterns and anomalies | Coralogix, Datadog, CloudWatch |
| **Metrics Analysis** | Identify metric anomalies | Prometheus, Grafana, Datadog |
| **Infrastructure Check** | Verify pod/service health | Kubernetes, AWS |
| **Root Cause Analysis** | Synthesize findings into diagnosis | LLM reasoning |

## Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SLACK TRIGGER                                │
│                                                                       │
│   User: @incidentfox why is checkout returning 500 errors?          │
│                                                                       │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                                   │
│                                                                       │
│   1. Parse Slack event                                               │
│   2. Identify team from channel                                      │
│   3. Load team config                                                │
│   4. Route to appropriate agent                                      │
│                                                                       │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       PLANNER AGENT                                   │
│                                                                       │
│   Creates investigation plan:                                        │
│   1. Query historical incidents (Snowflake)                         │
│   2. Analyze recent logs (Coralogix)                                │
│   3. Check K8s pod status                                           │
│   4. Analyze metrics for anomalies                                  │
│   5. Synthesize root cause                                          │
│                                                                       │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│   K8s Agent   │          │ Metrics Agent │          │ Investigation │
│               │          │               │          │     Agent     │
│ • Pod status  │          │ • Anomalies   │          │               │
│ • Events      │          │ • Dashboards  │          │ • Logs        │
│ • Resources   │          │ • Alerts      │          │ • Traces      │
└───────┬───────┘          └───────┬───────┘          └───────┬───────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      SLACK OUTPUT HANDLER                            │
│                                                                       │
│   Progressive updates via message edits:                            │
│   - Initial: "Investigation started..."                             │
│   - Phase 1: "Checking historical incidents... ✅"                  │
│   - Phase 2: "Analyzing logs... ✅"                                 │
│   - Phase 3: "Checking K8s... ✅"                                   │
│   - Final: Full report with findings                                │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Progressive Updates

The Slack message updates in real-time as investigation progresses:

### Initial State
```
🦊 IncidentFox Investigation

*Investigation Progress:*
⏳ Gathering context...
```

### During Investigation
```
🦊 IncidentFox Investigation

*Investigation Progress:*
✅ Snowflake: Historical incident patterns     [View]
✅ Coralogix: Error logs & traces              [View]
⏳ Kubernetes: Pod health & events
⏳ Root cause analysis
```

### Completed
```
🦊 IncidentFox Investigation
Incident: INC-2024-0456 | Severity: 🔴 Critical

*Investigation Progress:*
✅ Snowflake: Historical incident patterns     [View]
✅ Coralogix: Error logs & traces              [View]
✅ Kubernetes: Pod health & events             [View]
✅ Root cause analysis                         [View]

*Root Cause:*
Payment gateway connection pool exhaustion causing timeout errors.

*Timeline:*
• 14:20:00 - Connection pool warnings start
• 14:23:45 - First timeout errors
• 14:25:00 - Error rate exceeds 40%

*Recommendations:*
1. Increase connection pool size (currently 10, recommend 50)
2. Add circuit breaker for payment gateway
3. Scale payment service to 3 replicas

[🔧 Apply Fix] [📋 Full Report] [🚫 Dismiss]
```

## Interactive Elements

### View Buttons

Each completed phase has a "View" button that opens a modal with detailed findings:

```python
# When user clicks "View" on Coralogix phase
{
    "type": "modal",
    "title": "Coralogix — Logs",
    "blocks": [
        {"type": "section", "text": "Found 234 error logs in the last 15 minutes"},
        {"type": "section", "text": "Top error patterns:"},
        {"type": "section", "text": "• Connection timeout: 180 occurrences"},
        {"type": "section", "text": "• Pool exhausted: 54 occurrences"},
    ]
}
```

### Action Buttons

| Button | Action |
|--------|--------|
| **Apply Fix** | Triggers remediation workflow (with approval) |
| **Full Report** | Opens modal with complete investigation report |
| **Dismiss** | Marks investigation as reviewed |

## Configuration

### Team Settings

```json
{
  "notifications": {
    "default_slack_channel_id": "C0A4967KRBM",
    "investigation_style": "progressive",
    "show_preliminary_findings": true
  },
  "investigation": {
    "phases": ["historical", "logs", "metrics", "k8s", "rca"],
    "timeout_seconds": 300,
    "parallel_phases": true
  }
}
```

### Phase Customization

Teams can customize which investigation phases run:

```json
{
  "investigation": {
    "phases": {
      "snowflake_history": true,
      "coralogix_logs": true,
      "coralogix_metrics": true,
      "kubernetes": true,
      "root_cause_analysis": true
    }
  }
}
```

## Implementation

### Key Files

| File | Purpose |
|------|---------|
| `agent/src/ai_agent/integrations/slack_ui.py` | Block Kit message builders |
| `agent/src/ai_agent/integrations/slack_mrkdwn.py` | Markdown → Slack formatting |
| `agent/src/ai_agent/core/output_handlers/slack.py` | Slack output handler |
| `orchestrator/webhooks/slack_handlers.py` | Slack event routing |

### Phase Status Tracking

```python
# Track phase status during investigation
phase_status = {
    "snowflake_history": "pending",
    "coralogix_logs": "pending",
    "coralogix_metrics": "pending",
    "kubernetes": "pending",
    "root_cause_analysis": "pending",
}

# Update as phases complete
phase_status["snowflake_history"] = "done"
await update_slack_message(channel, ts, build_progress_section(phase_status))
```

### Building the Dashboard

```python
from ai_agent.integrations.slack_ui import (
    build_investigation_header,
    build_progress_section,
    build_findings_section,
    build_action_buttons,
)

# Compose the full message
blocks = []
blocks.extend(build_investigation_header(
    title="IncidentFox Investigation",
    incident_id="INC-2024-0456",
    severity="critical"
))
blocks.extend(build_progress_section(phase_status))
blocks.extend(build_findings_section(findings))
blocks.extend(build_action_buttons())

# Post to Slack
await slack_client.chat_postMessage(
    channel=channel_id,
    blocks=blocks,
    thread_ts=thread_ts
)
```

## Best Practices

1. **Keep updates frequent** - Update after each phase, not just at the end
2. **Show preliminary findings early** - Don't wait for full analysis
3. **Use thread replies** - Keep the main message clean, details in thread
4. **Preserve context** - Include incident ID and severity prominently
5. **Make actions obvious** - Clear buttons for next steps

## Error Handling

When a phase fails:

```
🦊 IncidentFox Investigation

*Investigation Progress:*
✅ Snowflake: Historical incident patterns     [View]
❌ Coralogix: Error logs & traces              [Retry]
    └─ Error: API timeout after 30s
⏳ Kubernetes: Pod health & events
⏳ Root cause analysis
```

Users can click "Retry" to re-run the failed phase.

## Related Documentation

- [Output Handlers](OUTPUT_HANDLERS.md) - Multi-destination output routing
- [Multi-Agent System](MULTI_AGENT_SYSTEM.md) - How agents coordinate
- [Integrations](INTEGRATIONS.md) - Backend configuration
