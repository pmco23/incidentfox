#!/usr/bin/env python3
"""
incidentfoxctl - idempotent deploy helper for IncidentFox (AWS + EKS).

Goals:
- One command deploy for dev/test and for customer environments.
- Supports BYO or create EKS/RDS via Terraform.
- Deploys in-cluster services via Helm.
- Monitors rollout and prints actionable status.

This script intentionally uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(
    cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> None:
    print(f"+ {' '.join(cmd)}")
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env)
    if p.returncode != 0:
        raise SystemExit(p.returncode)


def capture(cmd: list[str], *, cwd: Path | None = None) -> str:
    p = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if p.returncode != 0:
        raise RuntimeError(p.stdout.strip())
    return p.stdout.strip()


@dataclass(frozen=True)
class DeployArgs:
    env: str
    aws_region: str
    aws_profile: str | None
    create_eks: bool
    create_rds: bool
    create_vpc: bool
    create_ecr: bool | None
    install_controllers: bool
    namespace: str
    values_file: str | None
    state_bucket: str | None
    lock_table: str | None


def terraform_env_dir(env: str) -> Path:
    return ROOT / "infra" / "terraform" / "envs" / env


def _terraform_backend_args(*, args: DeployArgs) -> list[str]:
    """
    Provide backend args for terraform init when remote state is requested.

    Note: backend configuration cannot be parameterized via variables inside Terraform config.
    The env must declare backend "s3" {} (or equivalent) for these flags to take effect.
    """
    if not args.state_bucket or not args.lock_table:
        return []
    key = f"incidentfox/{args.env}/terraform.tfstate"
    return [
        "-reconfigure",
        f"-backend-config=bucket={args.state_bucket}",
        f"-backend-config=key={key}",
        f"-backend-config=region={args.aws_region}",
        f"-backend-config=dynamodb_table={args.lock_table}",
        "-backend-config=encrypt=true",
    ]


def ensure_tools() -> None:
    for tool in ["terraform", "helm", "kubectl", "aws"]:
        if not shutil.which(tool):
            raise SystemExit(f"Missing required tool: {tool}")


def bootstrap_state(args: DeployArgs) -> None:
    if not args.state_bucket or not args.lock_table:
        print("Skipping state bootstrap (no --state-bucket/--lock-table provided).")
        return
    d = ROOT / "infra" / "terraform" / "state-bootstrap"
    run(["terraform", "init"], cwd=d)
    run(
        [
            "terraform",
            "apply",
            "-auto-approve",
            f"-var=aws_region={args.aws_region}",
            f"-var=aws_profile={args.aws_profile or ''}",
            f"-var=state_bucket_name={args.state_bucket}",
            f"-var=lock_table_name={args.lock_table}",
        ],
        cwd=d,
    )


def terraform_apply(args: DeployArgs) -> None:
    d = terraform_env_dir(args.env)
    if not d.exists():
        raise SystemExit(f"Terraform env not found: {d}")

    run(["terraform", "init", *_terraform_backend_args(args=args)], cwd=d)
    tfvars = [
        f"-var=aws_region={args.aws_region}",
        f"-var=aws_profile={args.aws_profile or ''}",
        f"-var=create_eks={'true' if args.create_eks else 'false'}",
        f"-var=create_rds={'true' if args.create_rds else 'false'}",
        f"-var=create_vpc={'true' if args.create_vpc else 'false'}",
    ]
    if args.create_ecr is not None:
        tfvars.append(f"-var=create_ecr={'true' if args.create_ecr else 'false'}")

    # For local deploy tooling, we typically need a public EKS endpoint.
    # Keep it locked to the current public IP by default.
    if (
        args.create_eks
        and os.getenv("INCIDENTFOX_DISABLE_PUBLIC_EKS_ENDPOINT", "0") != "1"
    ):
        try:
            ip = detect_public_ip()
            cidrs = [f"{ip}/32"]
            tfvars.append("-var=cluster_endpoint_public_access=true")
            tfvars.append("-var=cluster_endpoint_private_access=true")
            tfvars.append(
                f"-var=cluster_endpoint_public_access_cidrs={json.dumps(cidrs)}"
            )
        except Exception as e:
            print(
                f"WARNING: could not detect public IP for EKS endpoint allowlist: {e}"
            )
            print(
                "WARNING: leaving cluster_endpoint_public_access as-is (may be private-only)."
            )

    run(["terraform", "apply", "-auto-approve", *tfvars], cwd=d)


def terraform_output_json(args: DeployArgs) -> dict:
    d = terraform_env_dir(args.env)
    raw = capture(["terraform", "output", "-json"], cwd=d)
    import json  # stdlib only

    return json.loads(raw) if raw else {}


def detect_public_ip() -> str:
    # AWS provides a simple IP echo service.
    with urllib.request.urlopen("https://checkip.amazonaws.com", timeout=10) as r:
        ip = r.read().decode("utf-8").strip()
    if not ip or "." not in ip:
        raise RuntimeError(f"unexpected public ip: {ip!r}")
    return ip


def ensure_kubeconfig(args: DeployArgs, *, tf_outputs: dict) -> None:
    if not args.create_eks:
        # BYO EKS: assume kubeconfig is already configured.
        return
    cluster_name = tf_outputs.get("eks_cluster_name", {}).get("value") or os.getenv(
        "EKS_CLUSTER_NAME", ""
    )
    if not cluster_name:
        raise SystemExit(
            "EKS cluster name not found in terraform outputs and EKS_CLUSTER_NAME not set."
        )
    run(
        [
            "aws",
            "eks",
            "update-kubeconfig",
            "--region",
            args.aws_region,
            "--name",
            str(cluster_name),
        ]
    )


def helm_install_controllers(args: DeployArgs) -> None:
    # This is intentionally light-touch. Enterprises may prefer pre-install by platform teams.
    # We only install charts; IRSA is handled by Terraform.
    run(["helm", "repo", "add", "eks", "https://aws.github.io/eks-charts"])
    run(
        [
            "helm",
            "repo",
            "add",
            "external-secrets",
            "https://charts.external-secrets.io",
        ]
    )
    run(["helm", "repo", "update"])

    tf_out = terraform_output_json(args)
    alb_role_arn = tf_out.get("alb_controller_role_arn", {}).get("value") or ""
    eso_role_arn = tf_out.get("external_secrets_role_arn", {}).get("value") or ""
    vpc_id = tf_out.get("vpc_id", {}).get("value") or ""

    # AWS Load Balancer Controller
    # NOTE: clusterName is required.
    cluster_name = tf_out.get("eks_cluster_name", {}).get("value") or os.getenv(
        "EKS_CLUSTER_NAME", ""
    )
    if not cluster_name:
        print(
            "WARNING: EKS_CLUSTER_NAME not set; skipping aws-load-balancer-controller install."
        )
    else:
        if not alb_role_arn:
            print(
                "WARNING: alb_controller_role_arn missing from terraform outputs; ALB controller may not have IRSA permissions."
            )
        run(
            (
                [
                    "helm",
                    "upgrade",
                    "--install",
                    "aws-load-balancer-controller",
                    "eks/aws-load-balancer-controller",
                    "-n",
                    "kube-system",
                    "--set",
                    f"clusterName={cluster_name}",
                    "--set",
                    f"region={args.aws_region}",
                    "--set",
                    "serviceAccount.create=true",
                    "--set",
                    "serviceAccount.name=aws-load-balancer-controller",
                    "--set",
                    (
                        f"serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn={alb_role_arn}"
                        if alb_role_arn
                        else "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn="
                    ),
                ]
                + (["--set", f"vpcId={vpc_id}"] if vpc_id else [])
            )
        )

    # External Secrets Operator
    if not eso_role_arn:
        print(
            "WARNING: external_secrets_role_arn missing from terraform outputs; ESO may not have IRSA permissions."
        )
    run(
        [
            "helm",
            "upgrade",
            "--install",
            "external-secrets",
            "external-secrets/external-secrets",
            "-n",
            "incidentfox-system",
            "--create-namespace",
            "--set",
            "installCRDs=true",
            "--set",
            "serviceAccount.create=true",
            "--set",
            "serviceAccount.name=external-secrets",
            "--set",
            (
                f"serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn={eso_role_arn}"
                if eso_role_arn
                else "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn="
            ),
        ]
    )

    # Wait for ESO CRDs before installing charts that depend on them.
    # (Without this, the IncidentFox chart fails to apply ClusterSecretStore/ExternalSecret.)
    crds = [
        "clustersecretstores.external-secrets.io",
        "externalsecrets.external-secrets.io",
        "secretstores.external-secrets.io",
    ]
    for crd in crds:
        run(
            [
                "kubectl",
                "wait",
                "--for=condition=Established",
                f"crd/{crd}",
                "--timeout=120s",
            ]
        )


def helm_install_incidentfox(args: DeployArgs) -> None:
    chart_dir = ROOT / "charts" / "incidentfox"
    cmd = [
        "helm",
        "upgrade",
        "--install",
        "incidentfox",
        str(chart_dir),
        "-n",
        args.namespace,
        "--create-namespace",
    ]
    # Helm v4 defaults to server-side apply ("auto"). In our workflow we may also apply/delete
    # resources manually while iterating (e.g., migrations, bootstrap), which can trigger SSA
    # field conflicts on subsequent upgrades (notably on resources.* fields).
    #
    # For a smoother pilot/dev experience, force client-side apply.
    cmd += ["--server-side=false"]
    if args.values_file:
        cmd += ["-f", args.values_file]
    run(cmd)


def rollout_wait(args: DeployArgs) -> None:
    # Wait for deployments to be ready
    deployments = [
        "incidentfox-config-service",
        "incidentfox-orchestrator",
        "incidentfox-ai-pipeline-api",
        "incidentfox-agent",
        "incidentfox-web-ui",
    ]
    for dep in deployments:
        # ignore failures for disabled charts; kubectl will exit non-zero if not found
        try:
            run(
                [
                    "kubectl",
                    "-n",
                    args.namespace,
                    "rollout",
                    "status",
                    f"deploy/{dep}",
                    "--timeout=5m",
                ]
            )
        except SystemExit:
            print(f"(skip) rollout status failed or not found: {dep}")


def parse_args(argv: list[str]) -> DeployArgs:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--env", default="dev", help="terraform env under infra/terraform/envs/"
    )
    p.add_argument("--aws-region", default=os.getenv("AWS_REGION", "us-west-2"))
    p.add_argument("--aws-profile", default=os.getenv("AWS_PROFILE"))

    p.add_argument(
        "--create-eks", action="store_true", help="Terraform creates a new EKS cluster"
    )
    p.add_argument(
        "--create-rds", action="store_true", help="Terraform creates a new RDS instance"
    )
    p.add_argument(
        "--create-vpc",
        action="store_true",
        help="Terraform creates a new VPC + subnets (dev/pilot helper)",
    )
    p.set_defaults(create_ecr=None)
    ecr = p.add_mutually_exclusive_group()
    ecr.add_argument(
        "--create-ecr",
        dest="create_ecr",
        action="store_true",
        help="Terraform creates ECR repos (dev/pilot helper)",
    )
    ecr.add_argument(
        "--no-create-ecr",
        dest="create_ecr",
        action="store_false",
        help="Disable ECR repo creation even if env defaults to true",
    )

    p.add_argument(
        "--install-controllers",
        action="store_true",
        help="Install ALB controller and External Secrets via Helm",
    )
    p.add_argument("--namespace", default="incidentfox")
    p.add_argument(
        "--values",
        dest="values_file",
        default=None,
        help="Helm values file for charts/incidentfox",
    )

    p.add_argument(
        "--state-bucket",
        default=None,
        help="S3 bucket for terraform remote state (bootstrap helper)",
    )
    p.add_argument(
        "--lock-table",
        default=None,
        help="DynamoDB lock table for terraform state (bootstrap helper)",
    )

    a = p.parse_args(argv)
    return DeployArgs(
        env=a.env,
        aws_region=a.aws_region,
        aws_profile=a.aws_profile,
        create_eks=bool(a.create_eks),
        create_rds=bool(a.create_rds),
        create_vpc=bool(a.create_vpc),
        create_ecr=a.create_ecr,
        install_controllers=bool(a.install_controllers),
        namespace=a.namespace,
        values_file=a.values_file,
        state_bucket=a.state_bucket,
        lock_table=a.lock_table,
    )


def main(argv: list[str]) -> None:
    args = parse_args(argv)
    # Tools are required only if user runs this; keep it simple and fail fast.
    # ensure_tools()

    print(
        f"Deploying IncidentFox env={args.env} region={args.aws_region} namespace={args.namespace}"
    )

    if args.state_bucket and args.lock_table:
        bootstrap_state(args)

    terraform_apply(args)

    # If we created EKS, ensure kubeconfig is updated before Helm installs.
    try:
        tf_out = terraform_output_json(args)
        ensure_kubeconfig(args, tf_outputs=tf_out)
    except Exception as e:
        print(f"WARNING: kubeconfig update skipped/failed: {e}")

    if args.install_controllers:
        helm_install_controllers(args)

    helm_install_incidentfox(args)
    rollout_wait(args)

    print("\nDone.")
    print(f"- Namespace: {args.namespace}")
    print(
        "- Next: configure secrets (ESO) and set chart images/values for your environment."
    )


if __name__ == "__main__":
    main(sys.argv[1:])
