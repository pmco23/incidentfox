"""Kubernetes tools for pod inspection and debugging."""

import json

from agents import function_tool
from kubernetes import client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException

from ..core.logging import get_logger

logger = get_logger(__name__)


def _get_k8s_client():
    """Get Kubernetes client."""
    try:
        k8s_config.load_kube_config()
    except (FileNotFoundError, k8s_config.ConfigException):
        # Fallback to in-cluster config if kubeconfig not found
        k8s_config.load_incluster_config()
    return client.CoreV1Api(), client.AppsV1Api()


@function_tool(strict_mode=False)
def get_pod_logs(
    pod_name: str,
    namespace: str = "default",
    container: str | None = None,
    tail_lines: int = 100,
) -> str:
    """
    Get logs from a Kubernetes pod.

    Args:
        pod_name: Name of the pod
        namespace: Kubernetes namespace
        container: Specific container name (optional)
        tail_lines: Number of log lines to retrieve

    Returns:
        Pod logs as JSON string
    """
    try:
        core_v1, _ = _get_k8s_client()
        logs = core_v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            container=container,
            tail_lines=tail_lines,
        )

        logger.info(
            "retrieved_pod_logs",
            pod_name=pod_name,
            namespace=namespace,
            lines=tail_lines,
        )
        return json.dumps({"pod": pod_name, "namespace": namespace, "logs": logs})

    except ApiException as e:
        logger.error("failed_to_get_pod_logs", error=str(e), pod=pod_name)
        return json.dumps({"error": str(e), "pod": pod_name, "namespace": namespace})


@function_tool(strict_mode=False)
def describe_pod(pod_name: str, namespace: str = "default") -> str:
    """
    Get detailed information about a pod.

    Args:
        pod_name: Name of the pod
        namespace: Kubernetes namespace

    Returns:
        Pod details as JSON string
    """
    try:
        core_v1, _ = _get_k8s_client()
        pod = core_v1.read_namespaced_pod(name=pod_name, namespace=namespace)

        result = {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "status": pod.status.phase,
            "node": pod.spec.node_name,
            "containers": [
                {
                    "name": c.name,
                    "image": c.image,
                    "ready": any(
                        cs.name == c.name and cs.ready
                        for cs in (pod.status.container_statuses or [])
                    ),
                    "restart_count": next(
                        (
                            cs.restart_count
                            for cs in (pod.status.container_statuses or [])
                            if cs.name == c.name
                        ),
                        0,
                    ),
                }
                for c in pod.spec.containers
            ],
            "conditions": [
                {"type": cond.type, "status": cond.status, "reason": cond.reason}
                for cond in (pod.status.conditions or [])
            ],
        }
        return json.dumps(result)

    except ApiException as e:
        logger.error("failed_to_describe_pod", error=str(e), pod=pod_name)
        return json.dumps({"error": str(e), "pod": pod_name, "namespace": namespace})


@function_tool(strict_mode=False)
def list_pods(
    namespace: str = "default",
    label_selector: str | None = None,
) -> str:
    """
    List pods in a namespace.

    Args:
        namespace: Kubernetes namespace
        label_selector: Label selector (e.g., "app=myapp")

    Returns:
        List of pod summaries as JSON string
    """
    try:
        core_v1, _ = _get_k8s_client()
        pods = core_v1.list_namespaced_pod(
            namespace=namespace,
            label_selector=label_selector,
        )

        result = {
            "namespace": namespace,
            "pod_count": len(pods.items),
            "pods": [
                {
                    "name": pod.metadata.name,
                    "status": pod.status.phase,
                    "ready": f"{sum(1 for cs in (pod.status.container_statuses or []) if cs.ready)}/{len(pod.spec.containers)}",
                    "restarts": sum(
                        cs.restart_count for cs in (pod.status.container_statuses or [])
                    ),
                    "age": str(pod.metadata.creation_timestamp),
                }
                for pod in pods.items
            ],
        }
        return json.dumps(result)

    except ApiException as e:
        logger.error("failed_to_list_pods", error=str(e), namespace=namespace)
        return json.dumps({"error": str(e), "namespace": namespace})


@function_tool(strict_mode=False)
def get_pod_events(pod_name: str, namespace: str = "default") -> str:
    """
    Get events related to a pod.

    Args:
        pod_name: Name of the pod
        namespace: Kubernetes namespace

    Returns:
        List of events as JSON string
    """
    try:
        core_v1, _ = _get_k8s_client()
        events = core_v1.list_namespaced_event(
            namespace=namespace,
            field_selector=f"involvedObject.name={pod_name}",
        )

        result = {
            "pod": pod_name,
            "namespace": namespace,
            "event_count": len(events.items),
            "events": [
                {
                    "type": event.type,
                    "reason": event.reason,
                    "message": event.message,
                    "count": event.count,
                    "first_timestamp": str(event.first_timestamp),
                    "last_timestamp": str(event.last_timestamp),
                }
                for event in events.items
            ],
        }
        return json.dumps(result)

    except ApiException as e:
        logger.error("failed_to_get_events", error=str(e), pod=pod_name)
        return json.dumps({"error": str(e), "pod": pod_name, "namespace": namespace})


@function_tool(strict_mode=False)
def describe_deployment(deployment_name: str, namespace: str = "default") -> str:
    """
    Get detailed information about a deployment.

    Args:
        deployment_name: Name of the deployment
        namespace: Kubernetes namespace

    Returns:
        Deployment details as JSON string
    """
    try:
        _, apps_v1 = _get_k8s_client()
        deployment = apps_v1.read_namespaced_deployment(
            name=deployment_name, namespace=namespace
        )

        result = {
            "name": deployment.metadata.name,
            "namespace": deployment.metadata.namespace,
            "replicas": {
                "desired": deployment.spec.replicas,
                "ready": deployment.status.ready_replicas or 0,
                "available": deployment.status.available_replicas or 0,
                "updated": deployment.status.updated_replicas or 0,
            },
            "strategy": deployment.spec.strategy.type,
            "selector": deployment.spec.selector.match_labels,
            "conditions": [
                {
                    "type": cond.type,
                    "status": cond.status,
                    "reason": cond.reason,
                    "message": cond.message,
                }
                for cond in (deployment.status.conditions or [])
            ],
        }
        return json.dumps(result)

    except ApiException as e:
        logger.error(
            "failed_to_describe_deployment", error=str(e), deployment=deployment_name
        )
        return json.dumps(
            {"error": str(e), "deployment": deployment_name, "namespace": namespace}
        )


@function_tool(strict_mode=False)
def get_deployment_history(deployment_name: str, namespace: str = "default") -> str:
    """
    Get deployment rollout history.

    Args:
        deployment_name: Name of the deployment
        namespace: Kubernetes namespace

    Returns:
        List of replica sets with revision history as JSON string
    """
    try:
        _, apps_v1 = _get_k8s_client()

        # Get replica sets for this deployment
        deployment = apps_v1.read_namespaced_deployment(
            name=deployment_name, namespace=namespace
        )
        selector = deployment.spec.selector.match_labels
        label_selector = ",".join([f"{k}={v}" for k, v in selector.items()])

        rs_list = apps_v1.list_namespaced_replica_set(
            namespace=namespace, label_selector=label_selector
        )

        history = []
        for rs in rs_list.items:
            revision = rs.metadata.annotations.get(
                "deployment.kubernetes.io/revision", "unknown"
            )
            history.append(
                {
                    "revision": revision,
                    "name": rs.metadata.name,
                    "replicas": rs.spec.replicas,
                    "ready": rs.status.ready_replicas or 0,
                    "created": str(rs.metadata.creation_timestamp),
                }
            )

        # Sort by revision
        history.sort(key=lambda x: x["revision"], reverse=True)
        return json.dumps(
            {"deployment": deployment_name, "namespace": namespace, "history": history}
        )

    except ApiException as e:
        logger.error(
            "failed_to_get_deployment_history", error=str(e), deployment=deployment_name
        )
        return json.dumps(
            {"error": str(e), "deployment": deployment_name, "namespace": namespace}
        )


@function_tool(strict_mode=False)
def describe_service(service_name: str, namespace: str = "default") -> str:
    """
    Get information about a Kubernetes service.

    Args:
        service_name: Name of the service
        namespace: Kubernetes namespace

    Returns:
        Service details including endpoints as JSON string
    """
    try:
        core_v1, _ = _get_k8s_client()
        service = core_v1.read_namespaced_service(
            name=service_name, namespace=namespace
        )

        # Get endpoints
        try:
            endpoints = core_v1.read_namespaced_endpoints(
                name=service_name, namespace=namespace
            )
            endpoint_list = []
            for subset in endpoints.subsets or []:
                for address in subset.addresses or []:
                    endpoint_list.append(
                        {
                            "ip": address.ip,
                            "ready": True,
                            "target": (
                                address.target_ref.name if address.target_ref else None
                            ),
                        }
                    )
        except:
            endpoint_list = []

        result = {
            "name": service.metadata.name,
            "namespace": service.metadata.namespace,
            "type": service.spec.type,
            "cluster_ip": service.spec.cluster_ip,
            "external_ips": service.spec.external_i_ps or [],
            "ports": [
                {
                    "name": port.name,
                    "port": port.port,
                    "target_port": str(port.target_port),
                    "protocol": port.protocol,
                }
                for port in service.spec.ports
            ],
            "selector": service.spec.selector or {},
            "endpoints": endpoint_list,
        }
        return json.dumps(result)

    except ApiException as e:
        logger.error("failed_to_describe_service", error=str(e), service=service_name)
        return json.dumps(
            {"error": str(e), "service": service_name, "namespace": namespace}
        )


@function_tool(strict_mode=False)
def get_pod_resource_usage(pod_name: str, namespace: str = "default") -> str:
    """
    Get resource usage for a pod (requires metrics-server).

    Args:
        pod_name: Name of the pod
        namespace: Kubernetes namespace

    Returns:
        CPU and memory usage as JSON string
    """
    try:
        from kubernetes import client

        api = client.CustomObjectsApi()

        metrics = api.get_namespaced_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            namespace=namespace,
            plural="pods",
            name=pod_name,
        )

        containers = []
        for container in metrics.get("containers", []):
            containers.append(
                {
                    "name": container["name"],
                    "cpu": container["usage"]["cpu"],
                    "memory": container["usage"]["memory"],
                }
            )

        result = {
            "pod": pod_name,
            "namespace": namespace,
            "timestamp": metrics.get("timestamp"),
            "containers": containers,
        }
        return json.dumps(result)

    except Exception as e:
        logger.error("failed_to_get_resource_usage", error=str(e), pod=pod_name)
        # Return graceful error - metrics-server might not be installed
        return json.dumps(
            {
                "error": "Metrics not available (metrics-server may not be installed)",
                "pod": pod_name,
                "namespace": namespace,
            }
        )
