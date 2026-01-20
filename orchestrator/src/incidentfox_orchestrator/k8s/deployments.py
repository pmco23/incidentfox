"""
Deployment management for dedicated agent pods.

Enterprise feature: Some teams may require dedicated agent deployments
for isolation, performance, or compliance reasons.

Each dedicated deployment includes:
1. Deployment with 1+ replicas
2. Service for internal routing
3. Optional HPA for autoscaling

Naming convention:
- Deployment: agent-dedicated-{org_id}-{team_node_id}
- Service: agent-dedicated-{org_id}-{team_node_id}
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

try:
    from kubernetes import client
    from kubernetes.client.rest import ApiException

    K8S_AVAILABLE = True
except ImportError:
    K8S_AVAILABLE = False
    ApiException = Exception  # type: ignore

from incidentfox_orchestrator.k8s.client import K8sClient, get_k8s_client


def _log(event: str, **fields) -> None:
    """Structured logging."""
    try:
        payload = {
            "service": "orchestrator",
            "module": "k8s.deployments",
            "event": event,
            **fields,
        }
        print(json.dumps(payload, default=str))
    except Exception:
        print(f"{event} {fields}")


def _sanitize_name(value: str) -> str:
    """Sanitize a string for use in K8s resource names."""
    return value.lower().replace("_", "-").replace(".", "-")[:63]


def _get_deployment_name(org_id: str, team_node_id: str) -> str:
    """Generate Deployment name for a dedicated team agent."""
    org_safe = _sanitize_name(org_id)[:20]
    team_safe = _sanitize_name(team_node_id)[:30]
    return f"agent-dedicated-{org_safe}-{team_safe}"


def create_dedicated_agent_deployment(
    org_id: str,
    team_node_id: str,
    *,
    replicas: int = 1,
    agent_image: Optional[str] = None,
    config_service_url: Optional[str] = None,
    cpu_request: str = "500m",
    memory_request: str = "1Gi",
    cpu_limit: str = "2",
    memory_limit: str = "4Gi",
    k8s_client: Optional[K8sClient] = None,
) -> Dict[str, Any]:
    """
    Create a dedicated Deployment and Service for a team's agent.

    This is an enterprise feature for teams requiring:
    - Resource isolation
    - Custom scaling
    - Compliance requirements

    Args:
        org_id: Organization ID
        team_node_id: Team node ID
        replicas: Number of replicas (default 1)
        agent_image: Docker image for the agent (default from env)
        config_service_url: URL to config service (default from env)
        cpu_request/limit: CPU resources
        memory_request/limit: Memory resources
        k8s_client: K8s client instance (optional)

    Returns:
        Dict with deployment and service metadata
    """
    if not K8S_AVAILABLE:
        _log("k8s_not_available", operation="create_dedicated_agent_deployment")
        return {"error": "kubernetes package not installed"}

    kc = k8s_client or get_k8s_client()
    name = _get_deployment_name(org_id, team_node_id)
    namespace = kc.namespace

    # Get configuration from environment
    image = agent_image or os.getenv("AGENT_IMAGE", "incidentfox/agent:latest")
    cfg_url = config_service_url or os.getenv(
        "CONFIG_SERVICE_URL", "http://config-service:8080"
    )

    labels = {
        "app.kubernetes.io/name": "incidentfox-agent",
        "app.kubernetes.io/component": "dedicated-agent",
        "app.kubernetes.io/managed-by": "incidentfox-orchestrator",
        "incidentfox.io/org-id": _sanitize_name(org_id),
        "incidentfox.io/team-node-id": _sanitize_name(team_node_id),
        "incidentfox.io/deployment-mode": "dedicated",
    }

    selector = {
        "app.kubernetes.io/name": "incidentfox-agent",
        "incidentfox.io/org-id": _sanitize_name(org_id),
        "incidentfox.io/team-node-id": _sanitize_name(team_node_id),
    }

    # Build Deployment
    deployment = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(
            name=name,
            namespace=namespace,
            labels=labels,
        ),
        spec=client.V1DeploymentSpec(
            replicas=replicas,
            selector=client.V1LabelSelector(match_labels=selector),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels=labels),
                spec=client.V1PodSpec(
                    service_account_name=os.getenv(
                        "AGENT_SERVICE_ACCOUNT", "incidentfox-agent"
                    ),
                    containers=[
                        client.V1Container(
                            name="agent",
                            image=image,
                            image_pull_policy="Always",
                            ports=[
                                client.V1ContainerPort(
                                    container_port=8000,
                                    name="http",
                                ),
                            ],
                            env=[
                                client.V1EnvVar(name="ORG_ID", value=org_id),
                                client.V1EnvVar(
                                    name="TEAM_NODE_ID", value=team_node_id
                                ),
                                client.V1EnvVar(
                                    name="CONFIG_SERVICE_URL", value=cfg_url
                                ),
                                client.V1EnvVar(
                                    name="DEPLOYMENT_MODE", value="dedicated"
                                ),
                            ],
                            resources=client.V1ResourceRequirements(
                                requests={"cpu": cpu_request, "memory": memory_request},
                                limits={"cpu": cpu_limit, "memory": memory_limit},
                            ),
                            readiness_probe=client.V1Probe(
                                http_get=client.V1HTTPGetAction(
                                    path="/health",
                                    port=8000,
                                ),
                                initial_delay_seconds=10,
                                period_seconds=10,
                            ),
                            liveness_probe=client.V1Probe(
                                http_get=client.V1HTTPGetAction(
                                    path="/health",
                                    port=8000,
                                ),
                                initial_delay_seconds=30,
                                period_seconds=30,
                            ),
                        )
                    ],
                ),
            ),
        ),
    )

    # Build Service
    service = client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=client.V1ObjectMeta(
            name=name,
            namespace=namespace,
            labels=labels,
        ),
        spec=client.V1ServiceSpec(
            type="ClusterIP",
            selector=selector,
            ports=[
                client.V1ServicePort(
                    name="http",
                    port=8000,
                    target_port=8000,
                    protocol="TCP",
                ),
            ],
        ),
    )

    result = {
        "name": name,
        "namespace": namespace,
        "org_id": org_id,
        "team_node_id": team_node_id,
        "replicas": replicas,
        "service_url": f"http://{name}.{namespace}.svc.cluster.local:8000",
    }

    try:
        # Create/update Deployment
        try:
            kc.apps_v1.create_namespaced_deployment(
                namespace=namespace, body=deployment
            )
            result["deployment_created"] = True
            _log("deployment_created", name=name, namespace=namespace)
        except ApiException as e:
            if e.status == 409:
                kc.apps_v1.replace_namespaced_deployment(
                    name=name, namespace=namespace, body=deployment
                )
                result["deployment_updated"] = True
                _log("deployment_updated", name=name, namespace=namespace)
            else:
                raise

        # Create/update Service
        try:
            kc.core_v1.create_namespaced_service(namespace=namespace, body=service)
            result["service_created"] = True
            _log("service_created", name=name, namespace=namespace)
        except ApiException as e:
            if e.status == 409:
                # Services can't be directly replaced; patch instead
                kc.core_v1.patch_namespaced_service(
                    name=name, namespace=namespace, body=service
                )
                result["service_updated"] = True
                _log("service_updated", name=name, namespace=namespace)
            else:
                raise

        return result

    except ApiException as e:
        _log(
            "dedicated_deployment_create_failed",
            name=name,
            namespace=namespace,
            error=str(e),
            status=getattr(e, "status", None),
        )
        return {
            **result,
            "error": str(e),
            "status": getattr(e, "status", None),
        }


def delete_dedicated_agent_deployment(
    org_id: str,
    team_node_id: str,
    *,
    k8s_client: Optional[K8sClient] = None,
) -> Dict[str, Any]:
    """
    Delete a team's dedicated agent Deployment and Service.

    Args:
        org_id: Organization ID
        team_node_id: Team node ID
        k8s_client: K8s client instance (optional)

    Returns:
        Dict with deletion status
    """
    if not K8S_AVAILABLE:
        _log("k8s_not_available", operation="delete_dedicated_agent_deployment")
        return {"error": "kubernetes package not installed"}

    kc = k8s_client or get_k8s_client()
    name = _get_deployment_name(org_id, team_node_id)
    namespace = kc.namespace

    result = {
        "name": name,
        "namespace": namespace,
        "org_id": org_id,
        "team_node_id": team_node_id,
    }

    # Delete Deployment
    try:
        kc.apps_v1.delete_namespaced_deployment(
            name=name,
            namespace=namespace,
            body=client.V1DeleteOptions(propagation_policy="Foreground"),
        )
        result["deployment_deleted"] = True
        _log("deployment_deleted", name=name, namespace=namespace)
    except ApiException as e:
        if e.status == 404:
            result["deployment_deleted"] = False
            result["deployment_reason"] = "not_found"
        else:
            result["deployment_error"] = str(e)
            _log("deployment_delete_failed", name=name, error=str(e))

    # Delete Service
    try:
        kc.core_v1.delete_namespaced_service(name=name, namespace=namespace)
        result["service_deleted"] = True
        _log("service_deleted", name=name, namespace=namespace)
    except ApiException as e:
        if e.status == 404:
            result["service_deleted"] = False
            result["service_reason"] = "not_found"
        else:
            result["service_error"] = str(e)
            _log("service_delete_failed", name=name, error=str(e))

    return result


def get_dedicated_agent_deployment(
    org_id: str,
    team_node_id: str,
    *,
    k8s_client: Optional[K8sClient] = None,
) -> Optional[Dict[str, Any]]:
    """
    Get information about a team's dedicated agent Deployment.

    Args:
        org_id: Organization ID
        team_node_id: Team node ID
        k8s_client: K8s client instance (optional)

    Returns:
        Dict with deployment info, or None if not found
    """
    if not K8S_AVAILABLE:
        return None

    kc = k8s_client or get_k8s_client()
    name = _get_deployment_name(org_id, team_node_id)
    namespace = kc.namespace

    try:
        dep = kc.apps_v1.read_namespaced_deployment(name=name, namespace=namespace)

        return {
            "name": dep.metadata.name,
            "namespace": dep.metadata.namespace,
            "replicas": dep.spec.replicas,
            "ready_replicas": dep.status.ready_replicas or 0,
            "available_replicas": dep.status.available_replicas or 0,
            "service_url": f"http://{name}.{namespace}.svc.cluster.local:8000",
            "conditions": [
                {
                    "type": c.type,
                    "status": c.status,
                    "reason": c.reason,
                }
                for c in (dep.status.conditions or [])
            ],
        }

    except ApiException as e:
        if e.status == 404:
            return None
        raise
