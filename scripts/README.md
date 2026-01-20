# IncidentFox E2E Test Scripts

Automated end-to-end testing for IncidentFox.

## Quick Start

```bash
# Quick health check (no secrets needed)
./health_check.sh

# Run all E2E tests
./e2e_test_all.sh

# Run specific tests
./e2e_test_all.sh slack           # Slack integration only
./e2e_test_all.sh otel cart       # Cart service fault only
./e2e_test_all.sh otel all        # All fault injection tests
```

## Scripts

### `health_check.sh`
Fast infrastructure validation without secrets.
- ✅ Kubernetes connectivity
- ✅ Pod status (agent, config-service, orchestrator, web-ui)
- ✅ Service existence
- ✅ Ingress and ALB provisioning
- ✅ External secrets sync
- ✅ HTTPS endpoints
- ✅ otel-demo availability

### `e2e_test_slack.py`
Full Slack integration test:
1. Posts a test message to Slack channel
2. Waits for agent response
3. Validates response in thread
4. Checks server-side logs

**Requirements:**
- `SLACK_BOT_TOKEN` in AWS Secrets Manager (`incidentfox/prod/slack_bot_token`)
- Slack channel ID configured

### `e2e_test_otel_demo.py`
Fault injection testing:
1. Injects a fault via flagd
2. Triggers agent investigation
3. Validates agent diagnosis
4. Clears the fault

**Available faults:**
- `cart` - Cart service failure
- `product` - Product catalog failure
- `recommendation` - Recommendation service failure
- `ad` - Ad service failure

### `e2e_test_all.sh`
Master test runner combining all tests.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_PROFILE` | `playground` | AWS profile for secrets |
| `AWS_REGION` | `us-west-2` | AWS region |
| `SLACK_CHANNEL_ID` | `C0A43KYJE03` | Slack channel for testing |
| `AGENT_NAMESPACE` | `incidentfox` | K8s namespace for IncidentFox |
| `OTEL_NAMESPACE` | `otel-demo` | K8s namespace for otel-demo |
| `WEB_UI_URL` | `https://ui.incidentfox.ai` | Web UI base URL |

## CI/CD Integration

Add to GitHub Actions:

```yaml
- name: Run E2E Tests
  run: |
    aws eks update-kubeconfig --name incidentfox-demo --region us-west-2
    ./scripts/health_check.sh
    ./scripts/e2e_test_all.sh
```

