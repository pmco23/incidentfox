from __future__ import annotations

"""
Question presets for validating a RAPTOR tree.

Notes:
- These are intended as *sanity checks*, not a formal benchmark.
- "Expected" is intentionally defined as keywords/phrases to look for, not exact strings.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class QACase:
    id: str
    question: str
    # If True, we expect the system can answer from Kubernetes concepts content.
    should_answer: bool
    # Substrings (case-insensitive) that should appear in a good answer.
    expected_contains: Optional[List[str]] = None


PRESETS: Dict[str, List[QACase]] = {
    # Kubernetes concepts-focused sanity checks (good coverage + easy to judge).
    "k8s_concepts_smoke": [
        QACase(
            id="configmap-what",
            question="What is a ConfigMap in Kubernetes and how is it used by pods?",
            should_answer=True,
            expected_contains=["configmap", "configuration", "pod"],
        ),
        QACase(
            id="secret-vs-configmap",
            question="What's the difference between a Secret and a ConfigMap?",
            should_answer=True,
            expected_contains=["secret", "configmap", "sensitive"],
        ),
        QACase(
            id="probes-diff",
            question="Explain the difference between liveness, readiness, and startup probes.",
            should_answer=True,
            expected_contains=["liveness", "readiness", "startup"],
        ),
        QACase(
            id="deployment-vs-statefulset",
            question="When should I use a Deployment vs a StatefulSet?",
            should_answer=True,
            expected_contains=["deployment", "statefulset"],
        ),
        QACase(
            id="service-types",
            question="Compare ClusterIP, NodePort, and LoadBalancer Services.",
            should_answer=True,
            expected_contains=["clusterip", "nodeport", "loadbalancer"],
        ),
        QACase(
            id="taints-vs-affinity",
            question="How are taints/tolerations different from node affinity?",
            should_answer=True,
            expected_contains=["taint", "toleration", "affinity"],
        ),
        QACase(
            id="pv-pvc-sc",
            question="Explain PersistentVolume (PV), PersistentVolumeClaim (PVC), and StorageClass and how they relate.",
            should_answer=True,
            expected_contains=["persistentvolume", "pvc", "storageclass"],
        ),
    ],
    # Out-of-domain: we expect "I don't know based on the provided context."
    "out_of_domain_smoke": [
        QACase(
            id="football",
            question="Who won the 2018 FIFA World Cup?",
            should_answer=False,
            expected_contains=["i don't know"],
        ),
        QACase(
            id="stock",
            question="What is Apple's stock price right now?",
            should_answer=False,
            expected_contains=["i don't know"],
        ),
        QACase(
            id="recipe",
            question="Give me a recipe for carbonara.",
            should_answer=False,
            expected_contains=["i don't know"],
        ),
    ],
    # Mixed quick preset (good for a 30s check).
    "quick_mix": [
        QACase(
            id="configmap-what",
            question="What is a ConfigMap in Kubernetes?",
            should_answer=True,
            expected_contains=["configmap"],
        ),
        QACase(
            id="football",
            question="Who won the 2018 FIFA World Cup?",
            should_answer=False,
            expected_contains=["i don't know"],
        ),
    ],
    # Broader coverage across the entire Kubernetes docs corpus.
    # Intended for "full ingest" runs (no filter-prefix).
    "k8s_full_curated_v1": [
        # Core objects / controllers
        QACase(
            id="deployment-vs-daemonset",
            question="When should I use a Deployment vs a DaemonSet?",
            should_answer=True,
            expected_contains=["deployment", "daemonset"],
        ),
        QACase(
            id="job-vs-cronjob",
            question="What's the difference between a Job and a CronJob?",
            should_answer=True,
            expected_contains=["job", "cronjob"],
        ),
        QACase(
            id="rs-vs-deployment",
            question="What is a ReplicaSet and how does it relate to a Deployment?",
            should_answer=True,
            expected_contains=["replicaset", "deployment"],
        ),
        # Scheduling
        QACase(
            id="node-selector-vs-affinity",
            question="Compare nodeSelector and node affinity.",
            should_answer=True,
            expected_contains=["nodeselector", "affinity"],
        ),
        QACase(
            id="pod-priority-preemption",
            question="What are Pod Priority and Preemption in Kubernetes?",
            should_answer=True,
            expected_contains=["priority", "preemption"],
        ),
        # Networking
        QACase(
            id="ingress-vs-gateway-api",
            question="What is the difference between Ingress and Gateway API?",
            should_answer=True,
            expected_contains=["ingress", "gateway"],
        ),
        QACase(
            id="dns-services",
            question="How does DNS work for Services and Pods in Kubernetes?",
            should_answer=True,
            expected_contains=["dns", "service"],
        ),
        # Storage
        QACase(
            id="access-modes",
            question="What do ReadWriteOnce, ReadOnlyMany, and ReadWriteMany mean for PersistentVolumes?",
            should_answer=True,
            expected_contains=["readwriteonce", "readonlymany", "readwritemany"],
        ),
        QACase(
            id="volume-snapshot",
            question="What is a VolumeSnapshot and how is it used?",
            should_answer=True,
            expected_contains=["volumesnapshot"],
        ),
        # Security / authn/z
        QACase(
            id="rbac-roles-bindings",
            question="Explain RBAC Roles, ClusterRoles, RoleBindings, and ClusterRoleBindings.",
            should_answer=True,
            expected_contains=["role", "clusterrole", "rolebinding"],
        ),
        QACase(
            id="serviceaccount-tokens",
            question="How do ServiceAccounts and their tokens work in Kubernetes?",
            should_answer=True,
            expected_contains=["serviceaccount", "token"],
        ),
        QACase(
            id="pod-security",
            question="What is Pod Security Admission (restricted/baseline/privileged) and how is it enforced?",
            should_answer=True,
            expected_contains=["pod", "security"],
        ),
        # Config / ops
        QACase(
            id="resource-requests-limits",
            question="What are CPU/memory requests and limits and how do they affect scheduling?",
            should_answer=True,
            expected_contains=["requests", "limits"],
        ),
        QACase(
            id="hpa",
            question="What is the HorizontalPodAutoscaler and what metrics can it use?",
            should_answer=True,
            expected_contains=["horizontalpodautoscaler", "metrics"],
        ),
        QACase(
            id="pdb",
            question="What is a PodDisruptionBudget and what does it protect against?",
            should_answer=True,
            expected_contains=["poddisruptionbudget"],
        ),
        # Observability
        QACase(
            id="events-vs-logs",
            question="What is the difference between Kubernetes Events and container logs?",
            should_answer=True,
            expected_contains=["events", "logs"],
        ),
        # Deliberate out-of-domain controls
        QACase(
            id="ood-math",
            question="Prove that there are infinitely many prime numbers.",
            should_answer=False,
            expected_contains=["i don't know"],
        ),
        QACase(
            id="ood-travel",
            question="Plan a 3-day itinerary for Paris with restaurant recommendations.",
            should_answer=False,
            expected_contains=["i don't know"],
        ),
    ],
}


def list_presets() -> List[str]:
    return sorted(PRESETS.keys())
