"""
Kubernetes client wrapper for Orchestrator.

Provides a unified interface for K8s operations with proper error handling
and environment-based configuration.
"""

from __future__ import annotations

import json
import os
from typing import Optional

try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException

    K8S_AVAILABLE = True
except ImportError:
    K8S_AVAILABLE = False
    ApiException = Exception  # type: ignore


def _log(event: str, **fields) -> None:
    """Structured logging."""
    try:
        payload = {"service": "orchestrator", "module": "k8s", "event": event, **fields}
        print(json.dumps(payload, default=str))
    except Exception:
        print(f"{event} {fields}")


class K8sClient:
    """
    Kubernetes client wrapper.

    Automatically loads config from:
    1. In-cluster config (when running in K8s)
    2. KUBECONFIG environment variable
    3. Default ~/.kube/config
    """

    def __init__(self, namespace: Optional[str] = None):
        if not K8S_AVAILABLE:
            raise RuntimeError(
                "kubernetes package not installed. Run: pip install kubernetes"
            )

        self._namespace = namespace or os.getenv("K8S_NAMESPACE", "incidentfox")
        self._loaded = False
        self._core_v1: Optional[client.CoreV1Api] = None
        self._apps_v1: Optional[client.AppsV1Api] = None
        self._batch_v1: Optional[client.BatchV1Api] = None

    def _ensure_loaded(self) -> None:
        """Lazy-load K8s configuration."""
        if self._loaded:
            return

        try:
            # Try in-cluster config first (running inside K8s)
            config.load_incluster_config()
            _log("k8s_config_loaded", source="incluster")
        except config.ConfigException:
            try:
                # Fall back to kubeconfig
                config.load_kube_config()
                _log("k8s_config_loaded", source="kubeconfig")
            except config.ConfigException as e:
                _log("k8s_config_failed", error=str(e))
                raise RuntimeError(f"Failed to load K8s config: {e}")

        self._core_v1 = client.CoreV1Api()
        self._apps_v1 = client.AppsV1Api()
        self._batch_v1 = client.BatchV1Api()
        self._loaded = True

    @property
    def namespace(self) -> str:
        return self._namespace

    @property
    def core_v1(self) -> client.CoreV1Api:
        self._ensure_loaded()
        return self._core_v1  # type: ignore

    @property
    def apps_v1(self) -> client.AppsV1Api:
        self._ensure_loaded()
        return self._apps_v1  # type: ignore

    @property
    def batch_v1(self) -> client.BatchV1Api:
        self._ensure_loaded()
        return self._batch_v1  # type: ignore


def get_k8s_client(namespace: Optional[str] = None) -> K8sClient:
    """Get a K8s client instance."""
    return K8sClient(namespace=namespace)


def is_k8s_available() -> bool:
    """Check if K8s client is available."""
    return K8S_AVAILABLE
