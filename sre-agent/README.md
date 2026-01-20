# SRE Agent (Premium)

**Production-ready AI SRE agent with Kubernetes sandboxing.**

The SRE Agent provides an additional runtime option using Claude Agent SDK with enterprise-grade isolation:

### Kubernetes Sandbox Isolation
- Each investigation runs in an isolated Kubernetes pod
- Automatic resource limits and network policies
- Session persistence for follow-up questions
- Secure credential injection via Kubernetes secrets

### Hybrid Session Management
- New requests create fresh sandboxes
- Follow-up requests reuse existing sandbox context
- Automatic cleanup after session timeout
- Audit logging of all agent actions

### Enterprise Features
- SOC 2 compliant isolation boundaries
- Air-gapped deployment support
- Custom sandbox images for your environment
- Integration with existing RBAC policies

---

**This is a premium feature.** For access, contact: **founders@incidentfox.ai**

[Learn more about IncidentFox Enterprise](https://incidentfox.ai)
