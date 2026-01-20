# MCP Per-Agent Tool Assignment - Configuration Guide

This guide explains how to configure MCP servers and assign specific tools to specific agents.

---

## Overview

IncidentFox supports two levels of MCP tool configuration:

1. **Team-Level**: Which MCP servers are available
2. **Agent-Level**: Which tools each agent can use

This gives you fine-grained control over which agents have access to which capabilities.

---

## Configuration Structure

```json
{
  "team_id": "your-team",

  // Step 1: Configure MCP Servers (Team Level)
  "mcp_servers": [
    {
      "id": "eks-mcp",
      "name": "AWS EKS MCP",
      "command": "uvx",
      "args": ["awslabs.eks-mcp-server@latest", "--allow-write", "--allow-sensitive-data-access"],
      "env": {
        "AWS_REGION": "us-east-1",
        "FASTMCP_LOG_LEVEL": "ERROR"
      }
    },
    {
      "id": "github-mcp",
      "name": "GitHub MCP",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {"GITHUB_TOKEN": "${github_token}"}
    }
  ],

  // Step 2: Assign Tools to Agents (Agent Level)
  "agent_tool_assignments": {
    "planner": {
      "mcp_tools": ["*"]  // Gets all MCP tools
    },
    "k8s_agent": {
      "mcp_tools": [
        "eks_mcp__*",  // All EKS tools
        "github_mcp__search_*"  // Only search tools from GitHub
      ]
    },
    "coding_agent": {
      "mcp_tools": [
        "github_mcp__*"  // All GitHub tools
      ]
    }
  }
}
```

---

## Use Cases & Examples

### Use Case 1: Give All Tools to Investigation Agents

**Scenario**: Investigation agents need access to everything to debug complex issues.

```json
{
  "agent_tool_assignments": {
    "planner": {
      "mcp_tools": ["*"]  // Wildcard = all tools
    },
    "investigation": {
      "mcp_tools": ["*"]  // Wildcard = all tools
    }
  }
}
```

---

### Use Case 2: Restrict K8s Agent to K8s Tools Only

**Scenario**: K8s agent should only have Kubernetes-related tools, not GitHub or Slack tools.

```json
{
  "mcp_servers": [
    {
      "id": "eks-mcp",
      "name": "AWS EKS MCP",
      "command": "uvx",
      "args": ["awslabs.eks-mcp-server@latest", "--allow-write", "--allow-sensitive-data-access"],
      "env": {
        "AWS_REGION": "us-east-1",
        "FASTMCP_LOG_LEVEL": "ERROR"
      }
    },
    {
      "id": "github-mcp",
      "name": "GitHub MCP",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {"GITHUB_TOKEN": "${github_token}"}
    }
  ],

  "agent_tool_assignments": {
    "k8s_agent": {
      "mcp_tools": [
        "eks_mcp__*"  // Only EKS tools (manage_eks_stacks, list_k8s_resources, etc.)
      ]
    }
  }
}
```

**Result**:
- K8s agent gets: 14 EKS tools
- K8s agent does NOT get: 51 GitHub tools

---

### Use Case 3: Coding Agent Gets Read-Only Tools

**Scenario**: Coding agent should read files but not write them.

```json
{
  "mcp_servers": [
    {
      "id": "filesystem-mcp",
      "name": "Filesystem MCP",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/app"],
      "env": {}
    }
  ],

  "agent_tool_assignments": {
    "coding_agent": {
      "mcp_tools": [
        "filesystem_mcp__read_file",
        "filesystem_mcp__list_directory",
        "filesystem_mcp__search_files"
      ]
      // Does NOT include write_file, edit_file, create_directory
    }
  }
}
```

**Result**:
- Coding agent can read files
- Coding agent cannot write/edit files

---

### Use Case 4: Different Tools for Different Agents

**Scenario**: Each agent type gets tools relevant to its specialty.

```json
{
  "mcp_servers": [
    {"id": "eks-mcp", ...},
    {"id": "github-mcp", ...},
    {"id": "slack-mcp", ...},
    {"id": "filesystem-mcp", ...}
  ],

  "agent_tool_assignments": {
    "planner": {
      "mcp_tools": ["*"]  // Orchestration agent gets everything
    },

    "k8s_agent": {
      "mcp_tools": [
        "eks_mcp__*"  // All Kubernetes/EKS tools
      ]
    },

    "coding_agent": {
      "mcp_tools": [
        "github_mcp__*",  // All GitHub tools
        "filesystem_mcp__read_*",  // Read-only filesystem tools
        "filesystem_mcp__list_*"
      ]
    },

    "investigation": {
      "mcp_tools": [
        "slack_mcp__*",  // All Slack tools (for communication)
        "filesystem_mcp__read_*"  // Read logs, etc.
      ]
    }
  }
}
```

---

### Use Case 5: Serkan's iHeartMedia Setup

**Scenario**: Serkan's coordinator bot delegates to IncidentFox, which should only use EKS tools.

```json
{
  "team_id": "iheart-media",

  "mcp_servers": [
    {
      "id": "eks-mcp",
      "name": "AWS EKS MCP",
      "command": "uvx",
      "args": ["awslabs.eks-mcp-server@latest", "--allow-write", "--allow-sensitive-data-access"],
      "env": {
        "AWS_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "${aws_access_key}",
        "AWS_SECRET_ACCESS_KEY": "${aws_secret_key}",
        "FASTMCP_LOG_LEVEL": "ERROR"
      }
    }
  ],

  // Serkan's coordinator delegates to IncidentFox planner
  "agent_tool_assignments": {
    "planner": {
      "mcp_tools": ["eks_mcp__*"]  // Only EKS tools
    },

    "k8s_agent": {
      "mcp_tools": ["eks_mcp__*"]  // Only EKS tools
    }
  }
}
```

**Flow**:
1. Serkan's coordinator: "Investigate EKS pod failures"
2. Coordinator delegates to IncidentFox via A2A
3. IncidentFox Planner uses EKS MCP tools
4. Planner discovers: manage_eks_stacks, list_k8s_resources, get_pod_logs, etc.
5. Planner investigates and returns results to coordinator

---

## Pattern Matching Syntax

Tool assignment patterns support Unix-style wildcards:

| Pattern | Matches | Example |
|---------|---------|---------|
| `*` | Everything | All tools from all MCPs |
| `eks_mcp__*` | All tools from EKS MCP | manage_eks_stacks, list_k8s_resources, ... |
| `*__read_*` | All read tools from any MCP | filesystem_mcp__read_file, github_mcp__read_file |
| `github_mcp__search_*` | All GitHub search tools | search_code, search_repositories |
| `filesystem_mcp__read_file` | Exact tool name | Only this specific tool |

---

## Default Behavior

If you don't specify `agent_tool_assignments`:
- ✅ All agents get all MCP tools (backward compatible)
- ✅ No filtering applied
- ✅ Works like before

```json
{
  "mcp_servers": [...]
  // No agent_tool_assignments
  // Result: All agents get all tools from all MCPs
}
```

---

## Testing Your Configuration

### Method 1: Check Logs

```bash
# Start agent with your config
# Look for these log messages:

mcp_tools_filtered_for_agent agent=k8s_agent total_tools=65 allowed_tools=14 patterns=['eks_mcp__*']
```

### Method 2: API Query

```bash
# Query effective config
curl https://config-service/api/v1/config/me \
  -H "Authorization: Bearer $TOKEN"

# Check agent_tool_assignments section
```

### Method 3: Run Test

```bash
cd agent
python -m pytest tests/test_mcp_per_agent_filtering.py -v
```

---

## Best Practices

### 1. Start Permissive, Then Restrict

```
Phase 1: Give all agents all tools
  → See what they actually use

Phase 2: Restrict based on usage patterns
  → Remove unused tools for security
```

### 2. Planner Should Get All Tools

```json
{
  "agent_tool_assignments": {
    "planner": {
      "mcp_tools": ["*"]  // Planner orchestrates, needs visibility
    }
  }
}
```

### 3. Specialized Agents Get Specialized Tools

```json
{
  "agent_tool_assignments": {
    "k8s_agent": {
      "mcp_tools": ["eks_mcp__*", "*__k8s__*"]
    },
    "aws_agent": {
      "mcp_tools": ["eks_mcp__*", "*__aws__*", "*__cloudwatch__*"]
    }
  }
}
```

### 4. Use Wildcards for Flexibility

```json
// Bad (too specific, breaks when tools are added)
{
  "mcp_tools": [
    "eks_mcp__manage_eks_stacks",
    "eks_mcp__list_k8s_resources",
    "eks_mcp__get_pod_logs"
  ]
}

// Good (flexible, automatically includes new tools)
{
  "mcp_tools": ["eks_mcp__*"]
}
```

---

## Troubleshooting

### Agent Not Getting Expected Tools

**Check**:
1. Is the MCP server connected? (Check logs for "mcp_connected")
2. Are tools discovered? (Check logs for "mcp_tools_discovered")
3. Is filtering configured? (Check agent_tool_assignments)
4. Do patterns match? (Check logs for "mcp_tools_filtered_for_agent")

**Debug Command**:
```bash
# Check what tools an agent gets
grep "mcp_tools_filtered_for_agent" agent.log | tail -5
```

---

### Tool Pattern Not Matching

**Common Issues**:
- Pattern: `"eks-mcp__*"` → Tool: `eks_mcp__tool` (underscore vs hyphen)
- Pattern: `"eks_mcp_*"` → Tool: `eks_mcp__tool` (single vs double underscore)
- Pattern: `"EKS_MCP__*"` → Tool: `eks_mcp__tool` (case-sensitive)

**Fix**: Use exact tool prefix from logs:
```bash
# Find exact tool names
grep "mcp_tool_registered" agent.log
```

---

## Security Considerations

### Dangerous Tools

Some MCP tools can be destructive. Restrict access carefully:

```json
{
  "agent_tool_assignments": {
    "investigation": {
      "mcp_tools": [
        "eks_mcp__get_*",  // Read-only
        "eks_mcp__list_*",  // Read-only
        "eks_mcp__describe_*"  // Read-only
      ]
      // Does NOT include:
      // - manage_eks_stacks (can delete clusters)
      // - terminate_* (destructive)
      // - delete_* (destructive)
    }
  }
}
```

### Principle of Least Privilege

Give agents only the tools they need:
- ✅ Investigation agent: Read-only tools
- ✅ K8s agent: K8s tools only
- ✅ Coding agent: GitHub + read-only filesystem
- ❌ Don't give all agents all tools (unless necessary)

---

## Migration Guide

### From: No Filtering (v0)

```json
{
  "mcp_servers": [...]
}
```

### To: With Filtering (v1)

```json
{
  "mcp_servers": [...],

  // Add agent assignments
  "agent_tool_assignments": {
    "planner": {"mcp_tools": ["*"]},
    "k8s_agent": {"mcp_tools": ["eks_mcp__*"]},
    "coding_agent": {"mcp_tools": ["github_mcp__*"]}
  }
}
```

**Migration is backward compatible**: Existing configs without `agent_tool_assignments` continue to work (all agents get all tools).

---

## FAQ

### Q: What happens if I don't specify agent_tool_assignments?

**A**: All agents get all tools from all MCP servers (default behavior).

### Q: Can I disable all MCP tools for an agent?

**A**: Yes, set `mcp_tools: []` (empty list).

```json
{
  "metrics_agent": {
    "mcp_tools": []  // No MCP tools, only built-in tools
  }
}
```

### Q: How do I see what tools an agent has?

**A**: Check logs for `mcp_tools_filtered_for_agent` message.

### Q: Do patterns support regex?

**A**: No, only Unix-style wildcards (`*`, `?`). Use `fnmatch` patterns.

### Q: Can I assign different tools from the same MCP to different agents?

**A**: Yes! Example:

```json
{
  "k8s_agent": {
    "mcp_tools": ["eks_mcp__get_*", "eks_mcp__list_*"]
  },
  "admin_agent": {
    "mcp_tools": ["eks_mcp__*"]  // Gets all EKS tools
  }
}
```

---

## Related Documentation

- [MCP Client Implementation](../docs/MCP_CLIENT_IMPLEMENTATION.md)
- [MCP Loader Configuration](../src/ai_agent/core/mcp_loader.py)
- [Tool Catalog](../docs/TOOLS_CATALOG.md)
