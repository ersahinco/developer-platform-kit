#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ACTIVE_CAPABILITY_AREAS = {
    "authn": "edge_auth",
    "authz": "authz_policy",
    "network": "network_connectivity",
    "ci_cd": "ci_cd_delivery",
    "observability": "observability_routing",
    "secrets": "secrets_injection",
    "service_identity": "service_identity",
}


@dataclass(frozen=True)
class EvidenceCheck:
    name: str
    status: str
    evidence: str


@dataclass(frozen=True)
class CapabilityProof:
    runtime_target: str
    area: str
    capability: str
    status: str
    checks: list[EvidenceCheck]


def _read_json(path: str) -> dict[str, Any]:
    data = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _exists(path: str) -> EvidenceCheck:
    exists = (ROOT / path).exists()
    return EvidenceCheck(
        name=path,
        status="ok" if exists else "fail",
        evidence="exists" if exists else "missing",
    )


def _contains(path: str, needle: str, *, name: str | None = None) -> EvidenceCheck:
    file_path = ROOT / path
    present = file_path.exists() and needle in file_path.read_text(encoding="utf-8")
    return EvidenceCheck(
        name=name or f"{path} contains {needle}",
        status="ok" if present else "fail",
        evidence=f"{path}: {needle}" if present else f"{path}: missing {needle}",
    )


def _capability_row(runtime_target: str, capability: str) -> EvidenceCheck:
    inventory = _read_json("platform/platform-inventory.json")
    rows = inventory["runtime_capabilities"]
    present = any(
        row["runtime_target"] == runtime_target and row["capability"] == capability
        for row in rows
    )
    return EvidenceCheck(
        name=f"{runtime_target}.{capability} capability row",
        status="ok" if present else "fail",
        evidence="platform/platform-inventory.json",
    )


def _runtime_default(runtime_target: str, area: str, capability: str) -> EvidenceCheck:
    defaults = _read_json("platform/runtime-defaults.json")
    actual = defaults["runtime_targets"][runtime_target]["defaults"][area]["capability"]
    ok = actual == capability
    return EvidenceCheck(
        name=f"{runtime_target}.{area} default maps to {capability}",
        status="ok" if ok else "fail",
        evidence=f"capability={actual}",
    )


def _primary_edge_auth_mode() -> EvidenceCheck:
    workloads = _read_json("platform/workloads.json")["workloads"]
    edge_modes = [
        workload["edge"]["auth_mode"]
        for workload in workloads
        if workload.get("name") == "api" and isinstance(workload.get("edge"), dict)
    ]
    ok = edge_modes == ["static-bearer-token"]
    return EvidenceCheck(
        name="primary edge workload declares static bearer auth",
        status="ok" if ok else "fail",
        evidence="platform/workloads.json api.edge.auth_mode",
    )


def _base_checks(runtime_target: str, area: str) -> list[EvidenceCheck]:
    capability = ACTIVE_CAPABILITY_AREAS[area]
    return [
        _runtime_default(runtime_target, area, capability),
        _capability_row(runtime_target, capability),
    ]


def _local_checks(area: str) -> list[EvidenceCheck]:
    if area == "authn":
        return [
            _primary_edge_auth_mode(),
            _contains("apps/api/main.py", "auth_status"),
            _contains(
                "tests/api/test_api_operational.py",
                "test_primary_edge_auth_enforces_bearer_token_when_configured",
            ),
            _contains("tests/api/test_api_operational.py", '"denied"'),
            _contains("tests/api/test_api_operational.py", '"succeeded"'),
        ]
    if area == "authz":
        return [
            _exists("platform/concerns/policy"),
            _contains("Makefile", "lint-policy"),
            _exists("tests/contracts/test_policy_contract.py"),
        ]
    if area == "network":
        return [
            _exists("compose.yaml"),
            _exists("platform/runtime-conformance.json"),
            _exists("tests/runtime/test_workload_conformance.py"),
            _contains("compose.yaml", "ports:"),
        ]
    if area == "ci_cd":
        return [
            _contains("Makefile", "platform-toolkit-validate-local"),
            _contains("Makefile", "runtime-conformance"),
            _exists("tests/contracts"),
        ]
    if area == "observability":
        return [
            _exists(
                "platform/concerns/observability/grafana/provisioning/datasources/"
                "datasources.yml"
            ),
            _contains(
                "platform/concerns/observability/grafana/provisioning/datasources/"
                "datasources.yml",
                "type: prometheus",
            ),
            _contains(
                "platform/concerns/observability/grafana/provisioning/datasources/"
                "datasources.yml",
                "type: loki",
            ),
            _contains(
                "platform/concerns/observability/grafana/provisioning/datasources/"
                "datasources.yml",
                "type: tempo",
            ),
            _contains(
                "tests/contracts/test_workload_observability_contract.py",
                "workload_info",
            ),
        ]
    if area == "secrets":
        return [
            _contains("platform/workloads.json", '"secrets"'),
            _contains("compose.yaml", "DB_PASSWORD"),
            _contains("Makefile", "secret-scan"),
        ]
    if area == "service_identity":
        return [
            _exists("compose.yaml"),
            _exists("platform/runtime-conformance.json"),
            _contains("tests/runtime/test_workload_conformance.py", "--network-alias"),
        ]
    raise ValueError(f"unsupported capability proof area: {area}")


def _local_kubernetes_checks(area: str) -> list[EvidenceCheck]:
    if area == "authn":
        return [
            _primary_edge_auth_mode(),
            _contains("infra/local-kubernetes/workloads.yaml", "PRIMARY_EDGE_AUTH_TOKEN"),
            _contains("apps/api/main.py", "auth_status"),
            _contains(
                "tests/api/test_api_operational.py",
                "test_primary_edge_auth_enforces_bearer_token_when_configured",
            ),
        ]
    if area == "authz":
        return [
            _exists("platform/concerns/policy"),
            _contains("Makefile", "lint-policy"),
            _exists("tests/contracts/test_policy_contract.py"),
        ]
    if area == "network":
        return [
            _exists("infra/local-kubernetes/kustomization.yaml"),
            _contains("infra/local-kubernetes/workloads.yaml", "kind: Service"),
            _contains("infra/local-kubernetes/workloads.yaml", "readinessProbe"),
            _contains("infra/local-kubernetes/workloads.yaml", "livenessProbe"),
            _contains("infra/local-kubernetes/runtime.yaml", "name: pgbouncer"),
        ]
    if area == "ci_cd":
        return [
            _contains("Makefile", "local-kubernetes-validate"),
            _contains("Makefile", "local-kubernetes-build"),
            _contains("Makefile", "local-kubernetes-smoke"),
            _exists("tests/contracts/test_local_kubernetes_contract.py"),
        ]
    if area == "observability":
        return [
            _contains("infra/local-kubernetes/workloads.yaml", "/metrics"),
            _contains("tests/contracts/test_workload_observability_contract.py", "workload_info"),
            _contains("Makefile", "kubectl logs"),
        ]
    if area == "secrets":
        return [
            _contains("platform/workloads.json", '"secrets"'),
            _contains("infra/local-kubernetes/runtime.yaml", "kind: Secret"),
            _contains("infra/local-kubernetes/workloads.yaml", "secretKeyRef"),
        ]
    if area == "service_identity":
        return [
            _contains("infra/local-kubernetes/runtime.yaml", "kind: ServiceAccount"),
            _contains("infra/local-kubernetes/workloads.yaml", "serviceAccountName"),
            _contains("infra/local-kubernetes/workloads.yaml", "runtime.target: local-kubernetes"),
            _contains("infra/local-kubernetes/workloads.yaml", "workload: api"),
        ]
    raise ValueError(f"unsupported capability proof area: {area}")


def _cloud_checks(area: str) -> list[EvidenceCheck]:
    if area == "authn":
        return [
            _primary_edge_auth_mode(),
            _contains("infra/app/workload_inventory.tf", "PRIMARY_EDGE_AUTH_TOKEN"),
            _contains(".github/workflows/app-deploy.yml", "auth_mode"),
            _contains("apps/api/main.py", "auth_status"),
            _contains("tests/api/test_api_operational.py", '"denied"'),
        ]
    if area == "authz":
        return [
            _exists("platform/concerns/policy/conftest"),
            _contains("Makefile", "lint-policy"),
            _exists("tests/contracts/test_policy_contract.py"),
        ]
    if area == "network":
        return [
            _exists("infra/platform/network.tf"),
            _contains("infra/app/compute_ecs.tf", "network_configuration"),
            _contains("infra/app/compute_ecs.tf", "private_subnet_ids"),
            _contains("infra/app/edge.tf", "aws_security_group"),
            _contains("infra/app/workload_jobs.tf", "network_configuration"),
        ]
    if area == "ci_cd":
        return [
            _contains("infra/platform/github_actions.tf", "oidc"),
            _contains(".github/workflows/app-build.yml", "id-token: write"),
            _contains(
                ".github/workflows/app-deploy.yml",
                "scripts.observability.release_event",
            ),
            _contains(".github/workflows/infra-plan.yml", "terraform plan"),
            _contains(".github/workflows/infra-apply.yml", "terraform apply"),
        ]
    if area == "observability":
        return [
            _contains("infra/app/variables.tf", "enable_adot_sidecar"),
            _contains("infra/app/observability.tf", "adot_collector_container"),
            _contains("infra/app/app_log_groups.tf", 'aws_cloudwatch_log_group" "adot'),
            _exists("scripts/observability/release_event.py"),
            _exists("scripts/observability/incident_evidence_bundle.py"),
        ]
    if area == "secrets":
        return [
            _contains("infra/app/workload_inventory.tf", "PRIMARY_EDGE_AUTH_TOKEN"),
            _contains("infra/app/providers.tf", "secretsmanager"),
            _exists("tests/contracts/test_platform_runtime_secret_contract.py"),
        ]
    if area == "service_identity":
        return [
            _exists("infra/app/runtime_identity.tf"),
            _contains(
                "infra/platform/github_actions.tf", "sts:AssumeRoleWithWebIdentity"
            ),
            _contains("infra/app/compute_ecs.tf", "task_role_arn"),
            _contains("infra/app/workload_jobs.tf", "task_role_arn"),
        ]
    raise ValueError(f"unsupported capability proof area: {area}")


def capability_proofs(runtime_target: str) -> list[CapabilityProof]:
    if runtime_target not in {"local-compose", "local-kubernetes", "aws-ecs"}:
        raise ValueError(
            "runtime target must be local-compose, local-kubernetes, or aws-ecs"
        )

    rows: list[CapabilityProof] = []
    for area, capability in ACTIVE_CAPABILITY_AREAS.items():
        checks = [
            *_base_checks(runtime_target, area),
            *(
                _local_checks(area)
                if runtime_target == "local-compose"
                else (
                    _local_kubernetes_checks(area)
                    if runtime_target == "local-kubernetes"
                    else _cloud_checks(area)
                )
            ),
        ]
        statuses = {check.status for check in checks}
        status = "fail" if "fail" in statuses else "ok"
        rows.append(
            CapabilityProof(
                runtime_target=runtime_target,
                area=area,
                capability=capability,
                status=status,
                checks=checks,
            )
        )
    return rows


def _print_text(rows: list[CapabilityProof]) -> None:
    for row in rows:
        print(f"{row.status:<4} {row.runtime_target} {row.area} {row.capability}")
        for check in row.checks:
            print(f"  {check.status:<4} {check.name}: {check.evidence}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize runtime capability proof evidence."
    )
    parser.add_argument(
        "--runtime-target",
        choices=["local-compose", "local-kubernetes", "aws-ecs"],
        required=True,
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    rows = capability_proofs(args.runtime_target)
    if args.format == "json":
        print(json.dumps([asdict(row) for row in rows], indent=2))
    else:
        _print_text(rows)
    return 1 if any(row.status == "fail" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
