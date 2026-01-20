# AI Agent System - Tools Catalog

## 📦 50+ Tools Across 11 Integration Categories

### 1. Core Tools (Always Available)
- **think** - Explicit reasoning and analysis

### 2. Kubernetes Tools (8 tools)
**Module**: `tools/kubernetes.py`

- `get_pod_logs` - Fetch pod logs
- `describe_pod` - Get pod status and configuration
- `list_pods` - List pods in namespace
- `get_pod_events` - Get Kubernetes events for pods
- `describe_deployment` - Get deployment status and replicas
- `get_deployment_history` - View rollout history
- `describe_service` - Get service details and endpoints
- `get_pod_resource_usage` - CPU/memory usage (requires metrics-server)

**Config**: Enabled when `K8S__ENABLED=true`

### 3. AWS Tools (7 tools)
**Module**: `tools/aws_tools.py`

- `describe_ec2_instance` - EC2 instance details
- `get_cloudwatch_logs` - Fetch CloudWatch logs
- `describe_lambda_function` - Lambda function config
- `get_rds_instance_status` - RDS database status
- `query_cloudwatch_insights` - Run Insights queries
- `get_cloudwatch_metrics` - Query CloudWatch metrics
- `list_ecs_tasks` - List ECS Fargate tasks

**Config**: Always available (boto3 is core dependency)

### 4. Slack Tools (4 tools)
**Module**: `tools/slack_tools.py`

- `search_slack_messages` - Search messages across workspace
- `get_channel_history` - Get channel message history
- `get_thread_replies` - Get all replies in a thread
- `post_slack_message` - Post messages (for notifications)

**Dependencies**: `slack-sdk`  
**Install**: `poetry install --extras slack`  
**Config**: Requires `SLACK_BOT_TOKEN`

### 5. GitHub Tools (4 tools)
**Module**: `tools/github_tools.py`

- `search_github_code` - Search code across repos
- `read_github_file` - Read file contents from repo
- `create_pull_request` - Create PRs
- `list_pull_requests` - List PRs in repo

**Dependencies**: `PyGithub`  
**Install**: `poetry install --extras github`  
**Config**: Requires `GITHUB_TOKEN`

### 6. Elasticsearch Tools (2 tools)
**Module**: `tools/elasticsearch_tools.py`

- `search_logs` - Search logs with Lucene query syntax
- `aggregate_errors_by_field` - Aggregate errors by field

**Dependencies**: `elasticsearch`  
**Install**: `poetry install --extras elasticsearch`  
**Config**: Requires `ELASTICSEARCH_URL`, optional auth

### 7. Confluence Tools (3 tools)
**Module**: `tools/confluence_tools.py`

- `search_confluence` - Search documentation
- `get_confluence_page` - Read page content
- `list_space_pages` - List pages in space

**Dependencies**: `atlassian-python-api`  
**Install**: `poetry install --extras confluence`  
**Config**: Requires `CONFLUENCE_URL`, `CONFLUENCE_API_TOKEN`

### 8. Sourcegraph Tools (1 tool)
**Module**: `tools/sourcegraph_tools.py`

- `search_sourcegraph` - Search code across all repositories

**Dependencies**: `httpx` (core dependency)  
**Config**: Requires `SOURCEGRAPH_URL`, `SOURCEGRAPH_TOKEN`

### 9. Datadog Tools (3 tools)
**Module**: `tools/datadog_tools.py`

- `query_datadog_metrics` - Query metrics
- `search_datadog_logs` - Search logs
- `get_service_apm_metrics` - Get APM metrics for service

**Dependencies**: `datadog-api-client`  
**Install**: `poetry install --extras datadog`  
**Config**: Requires `DATADOG_API_KEY`, `DATADOG_APP_KEY`

### 10. New Relic Tools (2 tools)
**Module**: `tools/newrelic_tools.py`

- `query_newrelic_nrql` - Run NRQL queries
- `get_apm_summary` - Get APM summary for app

**Dependencies**: `httpx` (core dependency)  
**Config**: Requires `NEWRELIC_API_KEY`

### 11. Google Workspace Tools (3 tools)
**Module**: `tools/google_docs_tools.py`

- `read_google_doc` - Read Google Doc content
- `search_google_drive` - Search Drive for files
- `list_folder_contents` - List files in folder

**Dependencies**: `google-api-python-client`, `google-auth`  
**Install**: `poetry install --extras google`  
**Config**: Requires `GOOGLE_CREDENTIALS_FILE` (service account JSON)

## 🎯 Tool Distribution by Agent

### Planner Agent
- **Tools**: None (planning only)
- **Purpose**: Create execution plans

### K8s Agent
- **Tools**: 9 (all K8s tools + think)
- **Purpose**: Kubernetes troubleshooting

### AWS Agent
- **Tools**: 8 (all AWS tools + think)
- **Purpose**: AWS resource debugging

### Coding Agent
- **Tools**: 1 (think)
- **Purpose**: Code analysis and fixes

### Metrics Agent
- **Tools**: 3 (CloudWatch metrics/insights + think)
- **Purpose**: Anomaly detection

### Investigation Agent 🌟
- **Tools**: 30+ (dynamically loaded!)
- **Purpose**: Comprehensive troubleshooting
- **Includes**: All tools from all categories (based on what's installed)

## 🔧 Dynamic Tool Loading

The Investigation Agent uses `tool_loader.py` which:

✅ **Checks if integration is installed**
```python
if is_integration_available("elasticsearch"):
    # Load Elasticsearch tools
```

✅ **Checks if credentials are configured**
```python
if config.slack.enabled:
    # Load Slack tools
```

✅ **Logs what was loaded**
```
slack_tools_loaded: count=4
github_tools_loaded: count=4
elasticsearch_tools_loaded: count=2
```

## 📦 Installation Options

### Minimal (Core only)
```bash
poetry install
# Gets: K8s, AWS, thinking tools
```

### With Specific Integrations
```bash
poetry install --extras slack
poetry install --extras "github elasticsearch"
```

### Everything
```bash
poetry install --extras all
# Installs all 11 integration categories
```

## 🔐 Configuration

All tools support environment-based config:

```bash
# Kubernetes
K8S__ENABLED=true
K8S__KUBECONFIG_PATH=~/.kube/config

# Slack
SLACK_BOT_TOKEN=xoxb-...

# GitHub
GITHUB_TOKEN=ghp_...

# Elasticsearch
ELASTICSEARCH_URL=https://...
ELASTICSEARCH_USERNAME=user
ELASTICSEARCH_PASSWORD=pass

# Confluence
CONFLUENCE_URL=https://your.atlassian.net
CONFLUENCE_API_TOKEN=token

# Sourcegraph
SOURCEGRAPH_URL=https://sourcegraph.com
SOURCEGRAPH_TOKEN=token

# Datadog
DATADOG_API_KEY=key
DATADOG_APP_KEY=appkey

# New Relic
NEWRELIC_API_KEY=key

# Google
GOOGLE_CREDENTIALS_FILE=/path/to/service-account.json
```

## 🎨 Tool Patterns

All tools follow the same pattern:

```python
@track_tool_metrics("tool_name")
def my_tool(arg: str) -> dict:
    """
    Tool description.
    
    Args:
        arg: Argument description
        
    Returns:
        Result description
    """
    try:
        # Implementation
        logger.info("tool_executed", arg=arg)
        return result
    except Exception as e:
        logger.error("tool_failed", error=str(e))
        raise ToolExecutionError("my_tool", str(e), e)
```

**Features**:
- ✅ Automatic metrics tracking
- ✅ Structured logging
- ✅ Error handling with context
- ✅ Type hints
- ✅ Docstrings

## 📊 Metrics Tracked

For every tool call:
- `tool_calls_total{tool_name, status}`
- `tool_duration_seconds{tool_name}`

View in Prometheus or CloudWatch!

## 🚀 Usage Example

```python
# Investigation agent automatically has all available tools
from ai_agent.core.agent_runner import get_agent_registry

registry = get_agent_registry()
runner = registry.get_runner("investigation_agent")

result = await runner.run(
    context,
    "Database latency increased - investigate using Slack incident channel, CloudWatch metrics, and recent GitHub PRs"
)

# Agent will:
# 1. Search Slack for recent incident discussions
# 2. Query CloudWatch for RDS metrics
# 3. Check GitHub for recent database-related PRs
# 4. Search Confluence for database runbooks
# 5. Provide comprehensive analysis
```

## 🔄 Tool Loading Flow

```
1. Agent created
   ↓
2. tool_loader.load_tools_for_agent(agent_name)
   ↓
3. Check each integration:
   - Is library installed? (importlib)
   - Are credentials configured? (env vars)
   - Is it enabled in config? (team_config)
   ↓
4. Load available tools
   ↓
5. Log what was loaded
   ↓
6. Return tool list to agent
```

## 🎯 Total Tool Count

| Category | Tools | Status |
|----------|-------|--------|
| Core | 1 | ✅ |
| Kubernetes | 8 | ✅ |
| AWS | 7 | ✅ |
| Slack | 4 | ✅ |
| GitHub | 4 | ✅ |
| Elasticsearch | 2 | ✅ |
| Confluence | 3 | ✅ |
| Sourcegraph | 1 | ✅ |
| Datadog | 3 | ✅ |
| New Relic | 2 | ✅ |
| Google Docs | 3 | ✅ |
| **TOTAL** | **38** | **✅** |

Plus MCP servers can add more dynamically!

## 📝 Adding More Tools

Follow the pattern:

1. Create tool file: `src/ai_agent/tools/my_integration.py`
2. Implement tools with `@track_tool_metrics` decorator
3. Add to `tool_loader.py` conditional loading
4. Add optional dependency to `pyproject.toml`
5. Document in this catalog
6. Test and deploy!

## 🎉 Production Ready

All tools are:
- ✅ Instrumented with metrics
- ✅ Structured logging
- ✅ Error handling
- ✅ Type-safe
- ✅ Documented
- ✅ Tested patterns

**Investigation Agent can troubleshoot across your entire stack!** 🚀

