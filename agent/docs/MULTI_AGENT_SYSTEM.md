# IncidentFox Multi-Agent System

## Architecture Overview

```
                    ┌─────────────────────────────────────────┐
                    │            Orchestrator                  │
                    │  (Slack/API → Agent Router)             │
                    └────────────────┬────────────────────────┘
                                     │
                    ┌────────────────▼────────────────────────┐
                    │           Agent Registry                 │
                    │  • Dynamic agent creation                │
                    │  • Team-specific config support          │
                    │  • Hot-reload on config changes          │
                    └────────────────┬────────────────────────┘
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        │                            │                            │
        ▼                            ▼                            ▼
┌───────────────┐          ┌─────────────────┐          ┌─────────────────┐
│   Planner     │          │  Investigation  │          │  Specialized    │
│   Agent       │◀────────▶│     Agent       │◀────────▶│    Agents       │
│               │          │                 │          │                 │
│  Orchestrates │          │  General SRE    │          │ K8s, AWS, Code  │
│  complex tasks│          │  Troubleshooting│          │ Metrics         │
└───────────────┘          └─────────────────┘          └─────────────────┘
```

## Agents Summary (6 Total)

| Agent | Purpose | Tools | Output Type |
|-------|---------|-------|-------------|
| **Planner** | Orchestrates complex multi-step tasks | None (plans only) | ExecutionPlan |
| **Investigation** | General SRE troubleshooting | 30+ tools (dynamic) | InvestigationResult |
| **K8s** | Kubernetes debugging | 9 K8s tools | K8sAnalysis |
| **AWS** | AWS resource debugging | 8 AWS tools | AWSAnalysis |
| **Metrics** | Anomaly detection | 3 CloudWatch tools | MetricsAnalysis |
| **Coding** | Code analysis/fixes | 1 (think) | CodingAnalysis |

---

## 1. Planner Agent

**Purpose**: Orchestrates complex tasks by routing work to specialized agents.

**Model Settings**: `temperature=0.3`

**Tools**: None (planning only)

**Output Schema**:
```python
class ExecutionPlan:
    goal: str                      # High-level goal
    strategy: str                  # Overall approach
    tasks: List[SubTask]           # Ordered sub-tasks
    parallel_execution: bool       # Can tasks run in parallel?
    estimated_total_minutes: int
    risks: List[str]               # Potential challenges
```

**System Prompt Summary**:
- Knows about all available expert agents
- Creates ordered execution plans with dependencies
- Identifies which agent handles which task
- Considers parallel execution opportunities
- Flags risks and estimates effort

---

## 2. Investigation Agent (Primary)

**Purpose**: Fast incident diagnosis and root cause analysis.

**Model Settings**: `temperature=0.4`

**Tools**: Dynamically loaded (30+):
- K8s: `list_pods`, `get_pod_logs`, `get_pod_events`, `describe_pod`, etc.
- AWS: `describe_ec2_instance`, `get_cloudwatch_logs`, `get_cloudwatch_metrics`, etc.
- Slack: `search_slack_messages`, `get_channel_history`, `post_slack_message`
- GitHub: `search_github_code`, `read_github_file`, `create_pull_request`
- And more...

**Output Schema**:
```python
class InvestigationResult:
    summary: str                   # Investigation summary
    root_cause: Optional[RootCause]  # {description, confidence, evidence}
    timeline: List[str]            # Event sequence
    affected_systems: List[str]    # Impacted services
    recommendations: List[str]     # Fix suggestions
    requires_escalation: bool
```

**System Prompt Summary**:
```
CRITICAL: Be EFFICIENT. Most issues can be diagnosed in 3-5 tool calls.

## INVESTIGATION WORKFLOW (Strict Order)
1. Get Overview (1-2 calls) - list_pods, look for errors
2. Get Details (1-2 calls) - get_pod_events, get_pod_logs  
3. STOP and Analyze - don't re-fetch
4. Return Structured Result

## RULES
- NEVER fetch same pod's logs more than once
- 3-5 tool calls is usually enough
- If you have evidence, STOP and REPORT
```

**Performance**: 15-25 second diagnosis, 86% accuracy

---

## 3. K8s Agent

**Purpose**: Kubernetes-specific troubleshooting.

**Model Settings**: `temperature=0.3`

**Tools (9)**:
| Tool | Purpose |
|------|---------|
| `think` | Reasoning step |
| `get_pod_logs` | Container logs |
| `describe_pod` | Pod details |
| `list_pods` | Pod listing |
| `get_pod_events` | K8s events |
| `get_pod_resource_usage` | CPU/memory |
| `describe_deployment` | Deployment status |
| `get_deployment_history` | Rollout history |
| `describe_service` | Service config |

**Output Schema**:
```python
class K8sAnalysis:
    summary: str
    pod_status: str
    issues_found: List[str]
    recommendations: List[str]
    requires_manual_intervention: bool
```

**System Prompt Summary**:
- Expert in: CrashLoopBackOff, OOMKills, ImagePullErrors
- 7-step investigation process
- Common issue patterns documented
- Provides specific kubectl commands

---

## 4. AWS Agent

**Purpose**: AWS resource debugging.

**Model Settings**: `temperature=0.3`

**Tools (8)**:
| Tool | Purpose |
|------|---------|
| `think` | Reasoning step |
| `describe_ec2_instance` | EC2 details |
| `describe_lambda_function` | Lambda config |
| `get_rds_instance_status` | RDS health |
| `list_ecs_tasks` | ECS tasks |
| `get_cloudwatch_logs` | Log retrieval |
| `query_cloudwatch_insights` | Log queries |
| `get_cloudwatch_metrics` | Metrics data |

**Output Schema**:
```python
class AWSAnalysis:
    summary: str
    resource_status: str
    issues_found: List[str]
    recommendations: List[str]
    estimated_cost_impact: Optional[str]
```

**System Prompt Summary**:
- Covers: EC2, Lambda, RDS, VPC, IAM
- Common patterns: Timeouts, permissions, connectivity
- Provides AWS CLI commands

---

## 5. Metrics Agent

**Purpose**: Anomaly detection and performance analysis.

**Model Settings**: `temperature=0.2` (analytical)

**Tools (3)**:
| Tool | Purpose |
|------|---------|
| `think` | Reasoning step |
| `get_cloudwatch_metrics` | Time-series data |
| `query_cloudwatch_insights` | Log queries |

**Output Schema**:
```python
class MetricsAnalysis:
    summary: str
    anomalies_found: List[Anomaly]  # {metric, timestamp, value, severity}
    baseline_established: bool
    recommendations: List[str]
    requires_immediate_action: bool
```

**System Prompt Summary**:
- Expertise: Time-series analysis, baseline detection
- Anomaly severity: Critical, High, Medium, Low
- CloudWatch Insights query examples

---

## 6. Coding Agent

**Purpose**: Code analysis and bug fixes.

**Model Settings**: `temperature=0.4`

**Tools (1)**:
| Tool | Purpose |
|------|---------|
| `think` | Reasoning step |

**Output Schema**:
```python
class CodingAnalysis:
    summary: str
    issues_found: List[str]
    code_changes: List[CodeChange]  # {file, change_type, description, snippet}
    testing_recommendations: List[str]
    explanation: str
```

**System Prompt Summary**:
- Focus: Bug fixing, optimization, refactoring
- Code quality principles
- Common bug patterns

---

## Evaluation Methodology

### Scoring Rubric (100 points)

| Dimension | Points | Criteria |
|-----------|--------|----------|
| **Root Cause** | 30 | Correct identification of fault |
| **Evidence** | 20 | Specific logs/events cited |
| **Impact** | 15 | Affected systems identified |
| **Timeline** | 15 | Event sequence reconstructed |
| **Recommendations** | 20 | Actionable fix suggestions |

### Test Scenarios

| Tier | Scenarios | Pass Criteria |
|------|-----------|---------------|
| 0 | Control (healthy check) | Correctly reports "healthy" |
| 1 | Pod crashes (cart, payment, ad) | Identifies crash + root cause |
| 2 | Feature flag faults | Identifies flag-induced failures |
| 3 | Performance issues (CPU, queue lag) | Identifies resource issues |
| 4 | Memory leaks, partial failures | Complex diagnosis |

### Achieved Results

| Scenario | Score | Time |
|----------|-------|------|
| healthCheck | 80/100 | 16s |
| cartCrash | 90/100 | 16s |
| paymentCrash | 85/100 | 24s |
| adCrash | 90/100 | 15s |
| **Average** | **86.2/100** | **18s** |

---

## Configuration

Agents support team-specific customization via Config Service:

```yaml
# Per-team agent config
agents:
  investigation_agent:
    enabled: true
    prompt: "Custom prompt..."  # Override system prompt
    timeout_seconds: 300
    max_retries: 3
    disable_default_tools: ["newrelic", "datadog"]
    enable_extra_tools: ["custom_tool"]
```

---

## Files

| File | Purpose |
|------|---------|
| `agents/registry.py` | Agent registration & creation |
| `agents/planner.py` | Planner agent definition |
| `agents/investigation_agent.py` | Investigation agent (primary) |
| `agents/k8s_agent.py` | Kubernetes agent |
| `agents/aws_agent.py` | AWS agent |
| `agents/metrics_agent.py` | Metrics analysis agent |
| `agents/coding_agent.py` | Code analysis agent |
| `tools/tool_loader.py` | Dynamic tool loading |
| `core/agent_runner.py` | Execution with retry/timeout |

---

*Last Updated: 2026-01-04*

