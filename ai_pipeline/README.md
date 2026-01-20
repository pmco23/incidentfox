# AI Pipeline (Premium)

**Continuous improvement system for IncidentFox agents.**

The AI Pipeline automatically improves your agents over time by analyzing team interactions and generating targeted updates:

### Bootstrap Phase (First Run)
Analyzes 90 days of historical data to create:
- Team-specific system prompts based on actual incident patterns
- MCP tool proposals for integrations your team frequently needs
- Initial knowledge base from team documentation

### Gap Analysis (Continuous)
Continuously monitors agent performance to detect:
- **Missing Tools**: "Agent couldn't query internal database"
- **Prompt Gaps**: "Agent didn't follow escalation policy"
- **Knowledge Gaps**: "Agent unaware of Service X dependency"
- **Behavior Gaps**: "Agent too verbose in responses"

### MCP Codegen (Approval-Gated)
- Automatically generates tool implementations from proposals
- Smoke testing with auto-repair (up to 3 attempts)
- Creates GitHub PRs for human review
- **No code deployed without approval**

---

**This is a premium feature.** For access, contact: **founders@incidentfox.ai**

[Learn more about IncidentFox Enterprise](https://incidentfox.ai)
