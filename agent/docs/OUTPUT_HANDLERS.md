# Agent Service - Output Handlers

Agent output can be sent to multiple destinations based on trigger source and team configuration.

---

## Overview

When an agent completes execution, results can be posted to:
- Slack channels (Block Kit rich UI)
- GitHub PR/Issue comments (Markdown)
- PagerDuty incident notes (future)
- Incident.io timeline (future)

---

## Output Destination Types

| Type | Description | Handler | Status |
|------|-------------|---------|--------|
| `slack` | Slack Block Kit message | `SlackOutputHandler` | ✅ Implemented |
| `github_pr_comment` | GitHub PR comment (markdown) | `GitHubPRCommentHandler` | ✅ Implemented |
| `github_issue_comment` | GitHub issue comment | `GitHubIssueCommentHandler` | ✅ Implemented |
| `pagerduty_note` | PagerDuty incident note | - | 🚧 Future |
| `incidentio_timeline` | Incident.io timeline entry | - | 🚧 Future |

---

## Default Output Routing

| Trigger Source | Default Output | Additional Options |
|----------------|----------------|-------------------|
| Slack @mention | Same Slack thread | - |
| GitHub PR/Issue | Same PR/Issue comment | Optionally Slack |
| PagerDuty alert | Team's default Slack channel | PagerDuty note |
| Incident.io | Team's default Slack channel | Incident.io timeline |
| API call | Team's default Slack channel | - |

---

## Team Configuration

Teams can configure output destinations in their config:

```json
{
  "notifications": {
    "default_slack_channel_id": "C0A4967KRBM",

    "github_output": {
      "slack_channel_id": "C_GITHUB_NOTIFICATIONS"
    },

    "pagerduty_output": {
      "slack_channel_id": "C_ONCALL",
      "post_pagerduty_note": true
    },

    "incidentio_output": {
      "slack_channel_id": null,
      "post_timeline": true
    }
  }
}
```

---

## API Usage

The agent API accepts `output_destinations` parameter:

```bash
POST /agents/planner/run
{
  "message": "Investigate high error rate",
  "output_destinations": [
    {
      "type": "slack",
      "channel_id": "C123",
      "thread_ts": "1234.5678",
      "user_id": "U123"
    },
    {
      "type": "github_pr_comment",
      "repo": "org/repo",
      "pr_number": 42
    }
  ]
}
```

Response:
```json
{
  "success": true,
  "output_mode": "destinations",
  "destinations_posted": ["slack", "github_pr_comment"]
}
```

---

## Slack Output Handler

### Features

- **Block Kit Rich UI**: Phase-based dashboard with real-time updates
- **Progressive Updates**: Updates message as investigation progresses
- **RCA Formatting**: Structured root cause analysis
- **Action Buttons**: Interactive remediation approval buttons

### Implementation

See: `agent/src/ai_agent/core/output_handlers/slack.py`

### Block Kit Dashboard Structure

```
┌─────────────────────────────────────────┐
│ 🔍 Investigation: High Error Rate       │
│ Incident: INC-123 | Severity: High      │
├─────────────────────────────────────────┤
│ ✅ Gathering Context                     │
│ ✅ Analyzing Logs                        │
│ 🔄 Identifying Root Cause                │
│ ⏳ Proposing Remediation                 │
├─────────────────────────────────────────┤
│ 📊 Findings:                             │
│ - Error spike started at 14:30           │
│ - Payment service deployment v2.3.1      │
│ - N+1 database query introduced          │
│                                          │
│ 🎯 Root Cause: Database Query Bug        │
│ Confidence: High (85%)                   │
│                                          │
│ 💡 Recommendations:                      │
│ 1. Rollback to v2.3.0                   │
│ 2. Fix N+1 query in payment handler     │
└─────────────────────────────────────────┘
```

---

## GitHub Output Handler

### Features

- **Markdown Formatting**: Clean, readable GitHub comments
- **Code Blocks**: Syntax-highlighted code snippets
- **Links**: Cross-references to logs, metrics, documentation

### Implementation

See: `agent/src/ai_agent/core/output_handlers/github.py`

### Example Output

```markdown
## 🔍 Investigation Results

### Findings

- Error spike detected at 14:30 UTC
- Related to deployment: payment-service v2.3.1
- Root cause: N+1 database query in payment handler

### Root Cause Analysis

**Issue**: Payment handler introduced N+1 query pattern

**Evidence**:
- Database query count increased 50x
- P95 latency: 150ms → 2500ms
- Deployment timing matches error spike

**Confidence**: High (85%)

### Recommendations

1. **Rollback to v2.3.0** (immediate)
2. **Fix N+1 query** - use eager loading in `PaymentHandler.process()`
3. **Add load testing** to catch similar issues in CI

**Generated by IncidentFox AI**
```

---

## Orchestrator Integration

The Orchestrator resolves output destinations using `OutputResolver`:

```python
# orchestrator/src/incidentfox_orchestrator/output_resolver.py

class OutputResolver:
    def resolve_destinations(
        self,
        trigger_source: str,
        trigger_context: dict,
        team_config: dict
    ) -> List[OutputDestination]:
        """
        Determine where agent output should be posted.

        Rules:
        1. If trigger has explicit destination (Slack thread, GitHub PR), use it
        2. Otherwise, use team's default destination for that trigger type
        3. Apply team's additional output rules
        """
```

See: `orchestrator/docs/SLACK_INTEGRATION.md` for full flow.

---

## Adding New Output Handlers

1. Create handler class: `agent/src/ai_agent/core/output_handlers/<type>.py`
2. Implement `OutputHandler` base class
3. Register in `agent/src/ai_agent/core/output_handler.py`
4. Add destination type to API schema
5. Update Orchestrator's `OutputResolver`

### Handler Interface

```python
from abc import ABC, abstractmethod

class OutputHandler(ABC):
    @abstractmethod
    async def post_result(
        self,
        result: AgentResult,
        destination: OutputDestination,
        format_options: dict
    ) -> bool:
        """
        Post agent result to destination.

        Returns:
            True if successful, False otherwise
        """
        pass
```

---

## Key Files

| File | Purpose |
|------|---------|
| `agent/src/ai_agent/core/output_handler.py` | Base handler and registry |
| `agent/src/ai_agent/core/output_handlers/slack.py` | Slack Block Kit output |
| `agent/src/ai_agent/core/output_handlers/github.py` | GitHub PR/issue comments |
| `agent/src/ai_agent/integrations/slack_ui.py` | Slack Block Kit builders |
| `agent/src/ai_agent/integrations/slack_mrkdwn.py` | Markdown → Slack formatting |
| `agent/src/ai_agent/core/slack_output.py` | Legacy Slack output (deprecated) |
| `orchestrator/src/incidentfox_orchestrator/output_resolver.py` | Destination resolution |

---

## Migration Notes

**Legacy vs New System**:
- ❌ Old: Agent directly posts to Slack via `SlackOutputHooks`
- ✅ New: Agent returns result, Orchestrator decides destinations

**Current State**: Both systems coexist during migration.

**Migration Path**:
1. Add `output_destinations` parameter to all webhook handlers
2. Update agent runners to use new output handlers
3. Remove `SlackOutputHooks` from agent code
4. Deprecate direct Slack posting in agent

---

## Testing

### Test Slack Output

```bash
# Trigger via webhook (Orchestrator resolves destination)
curl -X POST https://orchestrator.incidentfox.ai/webhooks/slack/events \
  -H "Content-Type: application/json" \
  -d '{...slack event...}'
```

### Test GitHub Output

```bash
# Trigger via GitHub webhook
curl -X POST https://orchestrator.incidentfox.ai/webhooks/github \
  -H "Content-Type: application/json" \
  -d '{...github webhook...}'
```

### Test API with Custom Destinations

```bash
curl -X POST http://agent:8080/api/v1/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Investigate error spike",
    "output_destinations": [
      {"type": "slack", "channel_id": "C123"},
      {"type": "github_pr_comment", "repo": "org/repo", "pr_number": 42}
    ]
  }'
```

---

## Future Enhancements

- **PagerDuty Notes**: Post investigation results to PD incident
- **Incident.io Timeline**: Add entries to incident timeline
- **Email Output**: Send formatted email summaries
- **Webhook Output**: POST results to custom webhook endpoints
- **Jira Comments**: Post to Jira tickets
- **Linear Comments**: Post to Linear issues
