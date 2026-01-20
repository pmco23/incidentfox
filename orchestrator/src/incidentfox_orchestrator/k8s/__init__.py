"""
Kubernetes operations for IncidentFox Orchestrator.

This module provides:
- CronJob management for AI Pipeline scheduling
- CronJob management for Dependency Discovery scheduling
- Deployment/Service management for dedicated agent pods (enterprise)
"""

from incidentfox_orchestrator.k8s.client import K8sClient
from incidentfox_orchestrator.k8s.cronjobs import (
    create_dependency_discovery_cronjob,
    create_pipeline_cronjob,
    delete_dependency_discovery_cronjob,
    delete_pipeline_cronjob,
    get_pipeline_cronjob,
)
from incidentfox_orchestrator.k8s.deployments import (
    create_dedicated_agent_deployment,
    delete_dedicated_agent_deployment,
    get_dedicated_agent_deployment,
)

__all__ = [
    "K8sClient",
    "create_pipeline_cronjob",
    "delete_pipeline_cronjob",
    "get_pipeline_cronjob",
    "create_dependency_discovery_cronjob",
    "delete_dependency_discovery_cronjob",
    "create_dedicated_agent_deployment",
    "delete_dedicated_agent_deployment",
    "get_dedicated_agent_deployment",
]
