# A2A Protocol Integration

**Agent-to-Agent (A2A) Protocol** enables IncidentFox agents to communicate with remote AI agents over HTTP using JSON-RPC 2.0.

## Overview

A2A allows you to:
- **Call remote agents as tools** - Delegate specialized tasks to external agents
- **Expose IncidentFox as an A2A server** - Let other agents call IncidentFox
- **Build multi-agent architectures** - Coordinate multiple specialized agents

```
┌─────────────────────────────────────────────────────────────────┐
│                    Coordinator Agent                              │
│                    (IncidentFox Planner)                          │
└────────────┬──────────────────────┬──────────────────────────────┘
             │                      │
             │ A2A                  │ A2A
             ▼                      ▼
┌────────────────────┐   ┌────────────────────────────────────────┐
│  Security Scanner  │   │  Compliance Checker                     │
│  (External Agent)  │   │  (External Agent)                       │
└────────────────────┘   └────────────────────────────────────────┘
```

## Configuration

### Adding Remote Agents

Configure remote A2A agents in your team configuration:

```json
{
  "remote_agents": {
    "security_scanner": {
      "type": "a2a",
      "name": "Security Scanner Agent",
      "description": "Scans code repositories for security vulnerabilities",
      "url": "https://security-agent.example.com/a2a",
      "auth": {
        "type": "bearer",
        "token": "sk-scanner-token-xxx"
      },
      "timeout": 300,
      "enabled": true
    },
    "compliance_checker": {
      "type": "a2a",
      "name": "Compliance Checker",
      "description": "Validates infrastructure against compliance frameworks",
      "url": "https://compliance.example.com/a2a",
      "auth": {
        "type": "api_key",
        "header": "X-API-Key",
        "key": "compliance-api-key"
      },
      "timeout": 600,
      "enabled": true
    }
  }
}
```

### Configuration Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"a2a"` |
| `name` | string | No | Human-readable agent name |
| `description` | string | No | What the agent does (shown in tool docs) |
| `url` | string | Yes | A2A endpoint URL |
| `auth` | object | No | Authentication configuration |
| `timeout` | number | No | Request timeout in seconds (default: 300) |
| `enabled` | boolean | No | Enable/disable agent (default: true) |

### Authentication Types

**Bearer Token:**
```json
{
  "auth": {
    "type": "bearer",
    "token": "your-bearer-token"
  }
}
```

**API Key (Header):**
```json
{
  "auth": {
    "type": "api_key",
    "header": "X-API-Key",
    "key": "your-api-key"
  }
}
```

**API Key (Query Parameter):**
```json
{
  "auth": {
    "type": "api_key_query",
    "param": "api_key",
    "key": "your-api-key"
  }
}
```

**No Authentication:**
```json
{
  "auth": {
    "type": "none"
  }
}
```

## Using Remote Agents

Once configured, remote agents appear as tools in your IncidentFox agent.

### Example: Planner Agent Using Security Scanner

```python
# The planner agent sees the tool as: call_security_scanner_agent(query: str)

# During an investigation, the planner can delegate:
Agent: "I need to check for security vulnerabilities in the affected service."

# Tool call:
call_security_scanner_agent(
    query="Scan the payments-service repository for SQL injection vulnerabilities"
)

# Returns:
{
  "status": "completed",
  "message": "Found 2 potential SQL injection vulnerabilities in payments-service...",
  "artifacts": [...]
}
```

### Automatic Tool Generation

When a remote agent is configured, IncidentFox automatically creates a tool function:

```python
# Tool function name: call_{agent_id}_agent
# Example: call_security_scanner_agent

def call_security_scanner_agent(query: str) -> str:
    """
    Call the remote Security Scanner Agent.

    Scans code repositories for security vulnerabilities

    Send a natural language query describing what you need.
    The remote agent will process it and return structured results.

    Args:
        query: Natural language description of the task

    Returns:
        JSON response from the remote agent
    """
```

## Exposing IncidentFox via A2A

IncidentFox can also act as an A2A server, allowing other agents to call it.

### Endpoint

```
POST /api/a2a
```

### Request Format

```json
{
  "jsonrpc": "2.0",
  "method": "tasks/send",
  "params": {
    "id": "task-123",
    "message": {
      "role": "user",
      "parts": [
        {"text": "Investigate why the checkout service is returning 500 errors"}
      ]
    },
    "sessionId": "session-456"
  },
  "id": "request-789"
}
```

### Supported Methods

| Method | Description |
|--------|-------------|
| `tasks/send` | Send a new task to the agent |
| `tasks/get` | Get status of an existing task |
| `tasks/cancel` | Cancel a running task |
| `agent/authenticatedExtendedCard` | Get agent capabilities card |

### Response Format

```json
{
  "jsonrpc": "2.0",
  "result": {
    "id": "task-123",
    "status": {
      "state": "completed",
      "message": {
        "role": "assistant",
        "parts": [
          {"text": "Investigation complete. Root cause: ..."}
        ]
      }
    },
    "artifacts": [
      {
        "type": "json",
        "name": "investigation_result",
        "data": {...}
      }
    ]
  },
  "id": "request-789"
}
```

### Task States

| State | Description |
|-------|-------------|
| `submitted` | Task received, waiting to start |
| `working` | Task is being processed |
| `completed` | Task finished successfully |
| `failed` | Task failed with error |
| `canceled` | Task was canceled |

## Use Cases

### 1. Hierarchical Multi-Agent Architecture

Use a coordinator agent to delegate to specialized sub-agents:

```
                    ┌─────────────────┐
                    │  Coordinator    │
                    │  (Planner)      │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ K8s Agent     │   │ Security Agent│   │ Metrics Agent │
│ (Local)       │   │ (A2A Remote)  │   │ (Local)       │
└───────────────┘   └───────────────┘   └───────────────┘
```

### 2. Cross-Organization Agent Federation

Connect agents across different organizations:

```json
{
  "remote_agents": {
    "partner_security_team": {
      "type": "a2a",
      "name": "Partner Security Team Agent",
      "url": "https://partner-org.example.com/a2a",
      "auth": {
        "type": "bearer",
        "token": "partner-federation-token"
      }
    }
  }
}
```

### 3. Specialized Domain Agents

Connect to domain-specific agents that have specialized knowledge:

```json
{
  "remote_agents": {
    "database_expert": {
      "type": "a2a",
      "name": "Database Expert Agent",
      "description": "Specializes in PostgreSQL and MySQL performance tuning",
      "url": "https://db-expert.example.com/a2a"
    },
    "network_analyzer": {
      "type": "a2a",
      "name": "Network Analyzer Agent",
      "description": "Analyzes network traffic patterns and identifies anomalies",
      "url": "https://network.example.com/a2a"
    }
  }
}
```

## Implementation Details

### Client Implementation

Location: `agent/src/ai_agent/integrations/a2a/client.py`

```python
from ai_agent.integrations.a2a.client import A2AClient, BearerAuth

# Create client
client = A2AClient(
    url="https://remote-agent.example.com/a2a",
    auth=BearerAuth("your-token"),
    timeout=300,
)

# Send task
result = await client.send_task("Investigate the error")

# Check status
status = await client.get_task_status(result["id"])

# Get agent capabilities
card = await client.get_agent_card()
```

### Polling Behavior

When a remote agent doesn't complete immediately:
1. Initial poll interval: 2 seconds
2. Exponential backoff: interval × 1.5 (capped at 10 seconds)
3. Timeout: configurable (default 5 minutes)

### Error Handling

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32600,
    "message": "Invalid Request"
  },
  "id": "request-789"
}
```

Common error codes:
| Code | Description |
|------|-------------|
| -32700 | Parse error |
| -32600 | Invalid request |
| -32601 | Method not found |
| -32602 | Invalid params |
| -32603 | Internal error |

## Configuration Inheritance

Remote agents follow the same inheritance pattern as other IncidentFox configurations:

```
Organization Config
└── remote_agents: {security_scanner: {...}}
    │
    ▼ (inherited)
Team Config
└── remote_agents: {
      security_scanner: {...},        # inherited
      compliance_checker: {...}       # team-specific
    }
```

Teams can:
- Inherit remote agents from org
- Add team-specific remote agents
- Override org agent settings
- Disable inherited agents (`"enabled": false`)

## Best Practices

1. **Set appropriate timeouts** - Long-running agents may need longer timeouts
2. **Use descriptive names** - Help your agent understand when to use each remote agent
3. **Provide good descriptions** - The description appears in tool documentation
4. **Handle failures gracefully** - Remote agents may be unavailable
5. **Use authentication** - Always authenticate remote agent calls in production

## Related Documentation

- [MCP Client Implementation](MCP_CLIENT_IMPLEMENTATION.md) - Another integration protocol
- [Multi-Agent System](MULTI_AGENT_SYSTEM.md) - Local multi-agent architecture
- [Config Inheritance](../../docs/CONFIG_INHERITANCE.md) - How configuration inheritance works
