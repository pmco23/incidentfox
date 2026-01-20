# Orchestrator - Slack Integration Flow

Complete flow from Slack @mention to agent response.

---

## Flow Diagram

```
1. User @mentions IncidentFox in Slack channel C0A4967KRBM
2. Slack → Orchestrator: POST /webhooks/slack/events
3. Orchestrator: Verify signature (SLACK_SIGNING_SECRET)
4. Orchestrator: Return 200 OK immediately (< 3s)
5. Orchestrator (async): Look up routing via Config Service
   ↓ POST /api/v1/internal/routing/lookup
   ↓ Response: org_id="extend", team_node_id="extend-sre", team_token="..."
6. Orchestrator: Get impersonation token for team
7. Orchestrator → Agent: POST /api/v1/agent/run
   ↓ Headers: Authorization: Bearer <team_token>
   ↓ Body: {message, slack_context: {channel, thread_ts, user_id}}
8. Agent: Post initial "🔍 Investigating..." message to Slack
9. Agent: Run planner → delegates to investigation agent
10. Agent: Update Slack message with phase progress (Block Kit)
11. Agent: Post final results with RCA and recommendations
```

---

## Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **Orchestrator** | Signature verification, routing lookup, return 200 OK < 3s |
| **Agent** | Rich Slack UI (Block Kit), tool execution, real-time updates |

---

## Why Agent Posts Directly

**Advantages**:
1. **Real-time updates**: Agent updates Slack message as phases complete
2. **Rich Block Kit UI**: Agent has `InvestigationOrchestrator` and `slack_ui.py`
3. **Single responsibility**: Agent owns output rendering, Orchestrator owns routing

**Alternative** (not used): Orchestrator could collect agent results and post to Slack, but this adds latency and complexity.

---

## Block Kit Dashboard

Agent uses progressive Block Kit updates:

```
[Phase 1: Gathering Context] ✅
[Phase 2: Analyzing Logs] 🔄 In Progress...
[Phase 3: Root Cause Analysis] ⏳ Pending
[Phase 4: Recommendations] ⏳ Pending
```

As each phase completes, the message updates in-place.

See: `/agent/docs/OUTPUT_HANDLERS.md` for Block Kit details.

---

## Slack Event Types

| Event | Description | Handler |
|-------|-------------|---------|
| `app_mention` | @IncidentFox mentioned | Trigger investigation |
| `message` | Message in channel | Ignored (requires @mention) |
| `reaction_added` | User reacts with emoji | Future: approve remediation |

---

## Slack Interactions

Button clicks and modal submissions:

```python
@app.post("/webhooks/slack/interactions")
async def slack_interactions(request: Request):
    payload = json.loads(form_data["payload"])

    if payload["type"] == "block_actions":
        # User clicked button (e.g., "Approve Restart")
        action = payload["actions"][0]
        if action["action_id"] == "approve_remediation":
            # Trigger remediation via Agent
            ...

    return {"ok": True}
```

---

## Configuration

Slack Bot Token stored in Kubernetes secret:

```bash
kubectl get secret incidentfox-slack -n incidentfox -o yaml
```

Required scopes:
- `app_mentions:read` - Receive @mentions
- `chat:write` - Post messages
- `chat:write.public` - Post to public channels
- `channels:history` - Read channel messages
- `channels:read` - List channels

---

## Testing

### Test @mention Flow

1. @mention IncidentFox in channel C0A4967KRBM
2. Check Orchestrator logs:
   ```bash
   kubectl logs -n incidentfox deploy/incidentfox-orchestrator --tail=50 -f
   ```
3. Check Agent logs:
   ```bash
   kubectl logs -n incidentfox deploy/incidentfox-agent --tail=50 -f
   ```
4. Verify Slack response appears in channel

### Simulate Webhook

```bash
curl -X POST http://localhost:8080/webhooks/slack/events \
  -H "Content-Type: application/json" \
  -H "X-Slack-Request-Timestamp: $(date +%s)" \
  -H "X-Slack-Signature: v0=<computed-signature>" \
  -d '{
    "event": {
      "type": "app_mention",
      "channel": "C0A4967KRBM",
      "user": "U123",
      "text": "<@BOT_ID> Investigate error spike",
      "ts": "1234567890.123456"
    }
  }'
```

---

## Related Documentation

- `/orchestrator/docs/WEBHOOKS.md` - Webhook routing details
- `/agent/docs/OUTPUT_HANDLERS.md` - Slack Block Kit output
- `/docs/ROUTING_DESIGN.md` - Routing architecture
