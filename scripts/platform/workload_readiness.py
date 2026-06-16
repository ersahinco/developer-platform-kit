#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tomllib
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.platform.workload_read_model import build_image_matrix  # noqa: E402
from scripts.platform.workload_read_model import workload_capabilities  # noqa: E402
from scripts.platform.workload_read_model import workload_repository  # noqa: E402
from scripts.platform.workload_read_model import workload_runtime_admitted  # noqa: E402
from scripts.platform.workload_read_model import workload_runtime_supported  # noqa: E402
from scripts.platform.workload_read_model import workloads  # noqa: E402
from scripts.platform.workload_runtime_config import (  # noqa: E402
    aws_env_realization_exception_names,
    declared_env_names,
)
from scripts.platform.local_kubernetes.admission import admission_rows  # noqa: E402


def _runtime_conformance() -> dict[str, Any]:
    return json.loads((ROOT / "platform" / "runtime-conformance.json").read_text())


def _workflow_texts() -> dict[str, str]:
    workflow_dir = ROOT / ".github" / "workflows"
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(workflow_dir.glob("*.yml"))
    }


def _yes(value: bool) -> str:
    return "yes" if value else "no"


def _shared_secret_names() -> set[str]:
    workload_inventory = ROOT / "infra" / "app" / "workload_inventory.tf"
    text = workload_inventory.read_text(encoding="utf-8")
    start = text.find("shared_secret_value_from = {")
    if start == -1:
        return set()
    body = text[start : text.find("\n  }", start)]
    names = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or "=" not in stripped:
            continue
        names.append(stripped.split("=", 1)[0].strip())
    return set(names)


def _local_compose_live_secret_names() -> set[str]:
    proof_script = ROOT / "scripts" / "platform" / "local_compose_live_proof.py"
    text = proof_script.read_text(encoding="utf-8")
    names = set()
    if 'env["PRIMARY_EDGE_AUTH_TOKEN"] = token' in text:
        names.add("PRIMARY_EDGE_AUTH_TOKEN")
    return names


def _local_kubernetes_secret_names() -> set[str]:
    root = ROOT / "infra" / "local-kubernetes"
    names: set[str] = set()
    for path in sorted(root.glob("*.yaml")):
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if not isinstance(document, dict):
                continue
            if document.get("kind") != "Secret":
                continue
            string_data = document.get("stringData", {})
            if isinstance(string_data, dict):
                names.update(str(name) for name in string_data)
    return names


def _local_kubernetes_config_names() -> set[str]:
    root = ROOT / "infra" / "local-kubernetes"
    names: set[str] = set()
    for path in sorted(root.glob("*.yaml")):
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if not isinstance(document, dict):
                continue
            if document.get("kind") != "ConfigMap":
                continue
            for key in ("data", "stringData"):
                values = document.get(key, {})
                if isinstance(values, dict):
                    names.update(str(name) for name in values)
    return names


def _workflow_mentions(workflow_texts: dict[str, str], *needles: str) -> list[str]:
    present = []
    filtered_needles = [needle for needle in needles if needle]
    for name, text in workflow_texts.items():
        if any(needle in text for needle in filtered_needles):
            present.append(name)
    return present


def _workflow_emits_evidence(text: str) -> bool:
    return "release-evidence-" in text or "operator-payload-" in text


def _targeted_support_evidence_workflow(workflow_texts: dict[str, str]) -> str | None:
    workflow = "data-support-deploy.yml"
    text = workflow_texts.get(workflow, "")
    if (
        _workflow_emits_evidence(text)
        and "target_workload" in text
        and 'evidence_workload_id="${{ inputs.target_workload }}"' in text
        and '--workload-id "$evidence_workload_id"' in text
    ):
        return workflow
    return None


def _app_deploy_has_related_workload_evidence(workflow_texts: dict[str, str]) -> bool:
    text = workflow_texts.get("app-deploy.yml", "")
    return (
        _workflow_emits_evidence(text)
        and "app_host_workloads" in text
        and "--related-workload-id" in text
    )


def _run_workflows(
    workload: dict[str, Any],
    *,
    workflow_texts: dict[str, str],
    aws_admitted: bool,
) -> str:
    if not aws_admitted:
        return "not-aws-admitted"

    capabilities = workload_capabilities(workload)
    if capabilities["edge_service"] or capabilities["internal_service"]:
        return "app-deploy.yml"
    if capabilities["scheduled_execution"]:
        return "data-support-deploy.yml"
    if capabilities["operator_execution"]:
        matches = _workflow_mentions(
            workflow_texts,
            str(workload["name"]),
            workload_repository(workload),
        )
        run_workflows = [
            workflow
            for workflow in matches
            if workflow
            not in {
                "app-build.yml",
                "data-support-deploy.yml",
                "infra-plan.yml",
                "security.yml",
            }
        ]
        return ",".join(run_workflows) if run_workflows else "missing"
    return "missing"


def _evidence(
    workload: dict[str, Any],
    *,
    workflow_texts: dict[str, str],
    aws_admitted: bool,
) -> str:
    if not aws_admitted:
        return "n/a"

    name = str(workload["name"])
    repository = workload_repository(workload)
    matches = _workflow_mentions(workflow_texts, name, repository)
    ignored_runtime_evidence_workflows = {
        "app-build.yml",
        "infra-plan.yml",
        "infra-apply.yml",
        "security.yml",
        "semgrep.yml",
        "local-kubernetes-contracts.yml",
    }
    evidence_workflows = [
        workflow
        for workflow in matches
        if workflow not in ignored_runtime_evidence_workflows
        and _workflow_emits_evidence(workflow_texts[workflow])
    ]
    capabilities = workload_capabilities(workload)
    if capabilities["edge_service"]:
        evidence_workflows.append("app-deploy.yml")
    if capabilities["internal_service"] and _app_deploy_has_related_workload_evidence(
        workflow_texts
    ):
        evidence_workflows.append("app-deploy.yml")
    if capabilities["scheduled_execution"]:
        support_workflow = _targeted_support_evidence_workflow(workflow_texts)
        if support_workflow is not None:
            evidence_workflows.append(support_workflow)
    return ",".join(sorted(set(evidence_workflows))) if evidence_workflows else "n/a"


def _rollback_proof(
    *,
    evidence: str,
    workflow_texts: dict[str, str],
    aws_admitted: bool,
) -> str:
    if not aws_admitted:
        return "not-aws-admitted"
    if evidence == "n/a":
        return "missing"

    categories: list[str] = []
    seen: set[str] = set()
    for workflow_name in evidence.split(","):
        text = workflow_texts.get(workflow_name, "")
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith("--rollback-category "):
                continue
            category = stripped.removeprefix("--rollback-category ").rstrip(" \\")
            if category and category not in seen:
                categories.append(category)
                seen.add(category)
    return ",".join(categories) if categories else "n/a"


def _proof_surface(
    *,
    local_compose: bool,
    local_kubernetes: bool,
    local_kubernetes_admission: str,
    aws_ecs_admitted: bool,
    evidence: str,
) -> str:
    surfaces = []
    if local_compose:
        surfaces.append("runtime-conformance")
    if local_kubernetes:
        surfaces.append(
            "local-kubernetes-evidence-drill"
            if local_kubernetes_admission == "ready"
            else "local-kubernetes-admission-report"
        )
    if aws_ecs_admitted and evidence != "n/a":
        surfaces.append("aws-ecs-evidence")
    return ",".join(surfaces) if surfaces else "missing"


def _policy_delivery_gate(*, aws_supported: bool, aws_admitted: bool) -> str:
    if aws_admitted:
        return "platform-toolkit-validate-cloud"
    if aws_supported:
        return "aws-admission-required"
    return "not-aws-supported"


def _terminal_events(
    workload: dict[str, Any],
    *,
    conformance: dict[str, Any],
) -> str:
    if workload.get("kind") != "job":
        return "n/a"
    fixture = conformance.get("workloads", {}).get(workload["name"], {})
    if not isinstance(fixture, dict):
        return "missing"
    event = fixture.get("expected_success_event")
    return event if isinstance(event, str) and event else "missing"


def _service_endpoints(workload: dict[str, Any]) -> str:
    if workload.get("kind") != "service":
        return "n/a"
    service = workload.get("service")
    metrics = workload.get("metrics")
    if isinstance(service, dict) and isinstance(metrics, dict):
        return "/health,/ready,/metrics"
    return "missing"


def _logs_contract(
    workload: dict[str, Any],
    *,
    conformance: dict[str, Any],
) -> str:
    fixture = conformance.get("workloads", {}).get(workload["name"], {})
    if not isinstance(fixture, dict):
        return "missing"
    event_key = (
        "expected_log_event"
        if workload.get("kind") == "service"
        else "expected_success_event"
    )
    event = fixture.get(event_key)
    fields = fixture.get("expected_log_fields")
    if not isinstance(event, str) or not event:
        return "missing"
    if not isinstance(fields, list):
        return "missing"
    values = [str(field) for field in fields if field]
    if "event" not in values:
        return "missing"
    return f"{event}:{','.join(values)}"


def _metrics_contract(workload: dict[str, Any]) -> str:
    if workload.get("kind") != "service":
        return "n/a"
    metrics = workload.get("metrics")
    if not isinstance(metrics, dict):
        return "missing"
    required_names = metrics.get("required_names")
    if metrics.get("format") != "prometheus" or not isinstance(required_names, list):
        return "missing"
    values = [str(name) for name in required_names if name]
    if "workload_info" not in values:
        return "missing"
    return ",".join(values) if values else "missing"


def _eventing_contract(workload: dict[str, Any]) -> str:
    dapr = workload.get("dapr")
    if not isinstance(dapr, dict):
        return "n/a"
    required_fields = ["app_id", "scope", "pubsub_name", "topic", "subscription_route"]
    if not all(
        isinstance(dapr.get(field), str) and dapr[field] for field in required_fields
    ):
        return "missing"
    if dapr.get("scope") != "pubsub":
        return "missing"
    return f"{dapr['pubsub_name']}:{dapr['topic']}"


def _idempotency_contract(workload: dict[str, Any]) -> str:
    if workload.get("kind") != "job":
        return "n/a"
    job = workload.get("job")
    if not isinstance(job, dict):
        return "missing"
    idempotency = job.get("idempotency")
    return (
        str(idempotency) if isinstance(idempotency, str) and idempotency else "missing"
    )


def _config_contract(workload: dict[str, Any]) -> str:
    config = workload.get("config")
    if not isinstance(config, dict):
        return "missing"
    env = config.get("env")
    secrets = config.get("secrets")
    return (
        "declared" if isinstance(env, list) and isinstance(secrets, list) else "missing"
    )


def _config_names(workload: dict[str, Any], key: str) -> str:
    config = workload.get("config")
    if not isinstance(config, dict):
        return "missing"
    names = config.get(key)
    if not isinstance(names, list):
        return "missing"
    values = [str(name) for name in names if name]
    return ",".join(values) if values else "none"


def _local_conformance_env_names(
    workload: dict[str, Any],
    *,
    conformance: dict[str, Any],
) -> set[str]:
    fixture = conformance.get("workloads", {}).get(workload["name"], {})
    if not isinstance(fixture, dict):
        return set()
    names: set[str] = set()
    if isinstance(workload.get("database"), dict):
        defaults = conformance.get("defaults", {}).get("env", {})
        if isinstance(defaults, dict):
            names.update(str(name) for name in defaults)
        names.add("DB_HOST")
    env = fixture.get("env", {})
    if isinstance(env, dict):
        names.update(str(name) for name in env)
    return names


def _aws_runtime_env_names(workload: dict[str, Any]) -> set[str]:
    names = set(aws_env_realization_exception_names(workload))
    declared = declared_env_names(workload)
    if isinstance(workload.get("database"), dict):
        names.update({"DB_HOST", "DB_PORT", "DB_USER", "DB_NAME"})
    if workload.get("traces", {}).get("supported") is True:
        names.update(
            {
                "OTEL_TRACES_ENABLED",
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
                "OTEL_SERVICE_NAME",
                "OTEL_DEPLOYMENT_ENVIRONMENT",
            }
        )
    if isinstance(workload.get("dapr"), dict):
        names.update(
            {
                "DAPR_HTTP_ENDPOINT",
                "DAPR_HTTP_PORT",
                "DAPR_PUBSUB_NAME",
                "DAPR_TOPIC",
                "DAPR_SUBSCRIPTION_ROUTE",
            }
        )
    if "DATA_EXPORT_S3_BUCKET" in declared:
        names.add("DATA_EXPORT_S3_BUCKET")
    return names


def _config_realization(
    workload: dict[str, Any],
    *,
    conformance: dict[str, Any],
    local_compose: bool,
    local_kubernetes: bool,
    aws_admitted: bool,
    local_kubernetes_config_names: set[str],
) -> str:
    declared = declared_env_names(workload)
    if not declared:
        return "none"

    surfaces = []
    if local_compose:
        surfaces.append(
            _config_surface(
                "local-compose",
                declared,
                _local_conformance_env_names(workload, conformance=conformance),
            )
        )
    if local_kubernetes:
        surfaces.append(
            _config_surface(
                "local-kubernetes",
                declared,
                local_kubernetes_config_names,
            )
        )
    if aws_admitted:
        surfaces.append(
            _config_surface("aws-ecs", declared, _aws_runtime_env_names(workload))
        )
    return ",".join(surfaces) if surfaces else "missing"


def _config_surface(
    runtime_target: str,
    declared: set[str],
    realized: set[str],
) -> str:
    missing = sorted(declared - realized)
    if missing:
        return f"{runtime_target}:missing:{'|'.join(missing)}"
    return runtime_target


def _declared_secret_names(workload: dict[str, Any]) -> set[str]:
    config = workload.get("config")
    if not isinstance(config, dict):
        return set()
    secrets = config.get("secrets")
    if not isinstance(secrets, list):
        return set()
    return {str(secret) for secret in secrets if secret}


def _local_conformance_secret_names(
    workload: dict[str, Any],
    *,
    conformance: dict[str, Any],
) -> set[str]:
    fixture = conformance.get("workloads", {}).get(workload["name"], {})
    if not isinstance(fixture, dict):
        return set()
    names: set[str] = set()
    if isinstance(workload.get("database"), dict):
        defaults = conformance.get("defaults", {}).get("secrets", {})
        if isinstance(defaults, dict):
            names.update(str(name) for name in defaults)
    secrets = fixture.get("secrets", {})
    if isinstance(secrets, dict):
        names.update(str(name) for name in secrets)
    return names


def _secret_injection(
    workload: dict[str, Any],
    *,
    conformance: dict[str, Any],
    local_compose: bool,
    local_kubernetes: bool,
    aws_admitted: bool,
    local_compose_live_secret_names: set[str],
    local_kubernetes_secret_names: set[str],
    aws_secret_names: set[str],
) -> str:
    declared = _declared_secret_names(workload)
    if not declared:
        return "none"

    surfaces = []
    if local_compose:
        injected = (
            _local_conformance_secret_names(
                workload,
                conformance=conformance,
            )
            | local_compose_live_secret_names
        )
        surfaces.append(_secret_surface("local-compose", declared, injected))
    if local_kubernetes:
        surfaces.append(
            _secret_surface("local-kubernetes", declared, local_kubernetes_secret_names)
        )
    if aws_admitted:
        surfaces.append(_secret_surface("aws-ecs", declared, aws_secret_names))
    return ",".join(surfaces) if surfaces else "missing"


def _secret_surface(
    runtime_target: str,
    declared: set[str],
    injected: set[str],
) -> str:
    missing = sorted(declared - injected)
    if missing:
        return f"{runtime_target}:missing:{'|'.join(missing)}"
    return runtime_target


def _use_cases(workload: dict[str, Any]) -> str:
    use_cases = workload.get("use_cases", [])
    if not isinstance(use_cases, list):
        return "missing"
    values = [str(use_case) for use_case in use_cases if use_case]
    return ",".join(values) if values else "missing"


def _compose_service_names(path: Path) -> set[str]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        return set()
    services = document.get("services", {})
    if not isinstance(services, dict):
        return set()
    return {str(name) for name in services}


def _catalog_targets(path: Path) -> set[str]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        return set()
    spec = document.get("spec", {})
    if not isinstance(spec, dict):
        return set()
    targets = spec.get("targets", [])
    if not isinstance(targets, list):
        return set()
    return {str(target).removeprefix("./") for target in targets}


def addition_rows() -> list[dict[str, str]]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    workspace_members = set(pyproject["tool"]["uv"]["workspace"]["members"])
    dockerfile = (ROOT / "platform" / "workload.Dockerfile").read_text(encoding="utf-8")
    compose_services = _compose_service_names(ROOT / "compose.yaml")
    catalog_targets = _catalog_targets(ROOT / "catalog-info.yaml")
    conformance = _runtime_conformance().get("workloads", {})

    rows = []
    for workload in workloads():
        name = str(workload["name"])
        app_path = str(workload["app_path"])
        repository = workload_repository(workload)
        app_root = ROOT / app_path
        required_files = ["main.py", "config.py", "pyproject.toml"]
        missing_app_files = [
            filename
            for filename in required_files
            if not (app_root / filename).exists()
        ]
        catalog_path = ROOT / "catalog" / f"{repository}-component.yaml"
        rows.append(
            {
                "workload": name,
                "app_files": (
                    "ok" if not missing_app_files else ",".join(missing_app_files)
                ),
                "uv_workspace": _yes(app_path in workspace_members),
                "dockerfile_copy": _yes(
                    f"COPY {app_path}/pyproject.toml {app_path}/pyproject.toml"
                    in dockerfile
                ),
                "compose_service": _yes(repository in compose_services),
                "runtime_conformance": _yes(name in conformance),
                "catalog_component": _yes(
                    catalog_path.exists()
                    and f"catalog/{repository}-component.yaml" in catalog_targets
                ),
                "app_tests": _yes(_has_app_tests(name)),
            }
        )
    return rows


def _has_app_tests(workload_name: str) -> bool:
    return (ROOT / "tests" / "apps" / workload_name).exists() or (
        workload_name == "api" and (ROOT / "tests" / "api").exists()
    )


def readiness_rows() -> list[dict[str, str]]:
    conformance = _runtime_conformance()
    workflow_texts = _workflow_texts()
    local_kubernetes_admissions = {row.workload: row for row in admission_rows()}
    local_compose_live_secret_names = _local_compose_live_secret_names()
    local_kubernetes_config_names = _local_kubernetes_config_names()
    local_kubernetes_secret_names = _local_kubernetes_secret_names()
    aws_secret_names = _shared_secret_names()
    aws_image_names = {
        image["name"]
        for image in build_image_matrix("sha-readiness", "pgbouncer-readiness")
        if image.get("name") not in {"liquibase", "pgbouncer"}
    }
    rows = []
    for workload in workloads():
        name = str(workload["name"])
        repository = workload_repository(workload)
        supported = set(workload_runtime_supported(workload))
        admitted = set(workload_runtime_admitted(workload))
        local_compose = "local-compose" in supported
        local_kubernetes = "local-kubernetes" in supported
        aws_supported = "aws-ecs" in supported
        aws_admitted = "aws-ecs" in admitted
        local_kubernetes_admission = (
            local_kubernetes_admissions[name].status
            if local_kubernetes and name in local_kubernetes_admissions
            else "n/a"
        )
        evidence = _evidence(
            workload,
            workflow_texts=workflow_texts,
            aws_admitted=aws_admitted,
        )
        rows.append(
            {
                "workload": name,
                "kind": str(workload.get("kind", "")),
                "class": str(workload.get("operational", {}).get("class", "")),
                "owner": str(workload.get("owner", "missing")),
                "use_cases": _use_cases(workload),
                "local_compose": _yes(local_compose),
                "local_kubernetes": _yes(local_kubernetes),
                "aws_ecs_supported": _yes(aws_supported),
                "aws_ecs_admitted": _yes(aws_admitted),
                "policy_delivery_gate": _policy_delivery_gate(
                    aws_supported=aws_supported,
                    aws_admitted=aws_admitted,
                ),
                "local_kubernetes_admission": local_kubernetes_admission,
                "proof_surface": _proof_surface(
                    local_compose=local_compose,
                    local_kubernetes=local_kubernetes,
                    local_kubernetes_admission=local_kubernetes_admission,
                    aws_ecs_admitted=aws_admitted,
                    evidence=evidence,
                ),
                "build_matrix": _yes(not aws_admitted or name in aws_image_names),
                "service_endpoints": _service_endpoints(workload),
                "logs_contract": _logs_contract(
                    workload,
                    conformance=conformance,
                ),
                "metrics_contract": _metrics_contract(workload),
                "eventing_contract": _eventing_contract(workload),
                "idempotency_contract": _idempotency_contract(workload),
                "job_terminal_event": _terminal_events(
                    workload,
                    conformance=conformance,
                ),
                "run_workflow": _run_workflows(
                    workload,
                    workflow_texts=workflow_texts,
                    aws_admitted=aws_admitted,
                ),
                "evidence": evidence,
                "rollback_proof": _rollback_proof(
                    evidence=evidence,
                    workflow_texts=workflow_texts,
                    aws_admitted=aws_admitted,
                ),
                "log_group": (
                    f"/ecs/<stack>/{repository}" if aws_admitted else "not-aws-admitted"
                ),
                "config_contract": _config_contract(workload),
                "config_env": _config_names(workload, "env"),
                "config_realization": _config_realization(
                    workload,
                    conformance=conformance,
                    local_compose=local_compose,
                    local_kubernetes=local_kubernetes,
                    aws_admitted=aws_admitted,
                    local_kubernetes_config_names=local_kubernetes_config_names,
                ),
                "secret_injection": _secret_injection(
                    workload,
                    conformance=conformance,
                    local_compose=local_compose,
                    local_kubernetes=local_kubernetes,
                    aws_admitted=aws_admitted,
                    local_compose_live_secret_names=local_compose_live_secret_names,
                    local_kubernetes_secret_names=local_kubernetes_secret_names,
                    aws_secret_names=aws_secret_names,
                ),
                "secret_names": _config_names(workload, "secrets"),
            }
        )
    return rows


def readiness_failures(rows: list[dict[str, str]]) -> list[str]:
    failures: list[str] = []
    for row in rows:
        workload = row["workload"]

        if row["owner"] in {"", "missing"}:
            failures.append(f"{workload}: workload lacks portable owner")
        if row["use_cases"] == "missing":
            failures.append(f"{workload}: workload lacks target-neutral use cases")

        if row["local_compose"] == "yes":
            if row["config_contract"] != "declared":
                failures.append(f"{workload}: local workload lacks config contract")
            if row["kind"] == "service" and row["service_endpoints"] == "missing":
                failures.append(
                    f"{workload}: local service lacks /health, /ready, or /metrics"
                )
            if row["kind"] == "service" and row["metrics_contract"] == "missing":
                failures.append(f"{workload}: local service lacks metrics contract")
            if row["logs_contract"] == "missing":
                failures.append(f"{workload}: local workload lacks logs contract")
            if "local-compose:missing:" in row["config_realization"]:
                failures.append(f"{workload}: local Compose lacks config realization")
            if "local-kubernetes:missing:" in row["config_realization"]:
                failures.append(
                    f"{workload}: local Kubernetes lacks config realization"
                )
            if "local-compose:missing:" in row["secret_injection"]:
                failures.append(
                    f"{workload}: local Compose lacks secret injection proof"
                )
            if "local-kubernetes:missing:" in row["secret_injection"]:
                failures.append(
                    f"{workload}: local Kubernetes lacks secret injection proof"
                )
            if row["kind"] == "job" and row["job_terminal_event"] == "missing":
                failures.append(f"{workload}: local job lacks terminal success event")
            if row["kind"] == "job" and row["idempotency_contract"] == "missing":
                failures.append(f"{workload}: local job lacks idempotency contract")
            if row["eventing_contract"] == "missing":
                failures.append(f"{workload}: local eventing contract is incomplete")

        if row["aws_ecs_admitted"] != "yes":
            continue

        required_fields = {
            "build_matrix": "AWS-admitted workload is missing image build coverage",
            "config_contract": "AWS-admitted workload lacks config contract",
        }
        for field, message in required_fields.items():
            expected = "yes" if field == "build_matrix" else "declared"
            if row[field] != expected:
                failures.append(f"{workload}: {message}")

        if row["run_workflow"] in {"missing", "not-aws-admitted"}:
            failures.append(f"{workload}: AWS-admitted workload lacks run workflow")
        if row["evidence"] == "n/a":
            failures.append(f"{workload}: AWS-admitted workload lacks evidence surface")
        if row["rollback_proof"] in {"missing", "n/a"}:
            failures.append(f"{workload}: AWS-admitted workload lacks rollback proof")
        if not row["log_group"].startswith("/ecs/<stack>/"):
            failures.append(
                f"{workload}: AWS-admitted workload lacks log group convention"
            )
        if row["logs_contract"] == "missing":
            failures.append(f"{workload}: AWS-admitted workload lacks logs contract")
        if "aws-ecs:missing:" in row["config_realization"]:
            failures.append(
                f"{workload}: AWS-admitted workload lacks config realization"
            )
        if "aws-ecs:missing:" in row["secret_injection"]:
            failures.append(
                f"{workload}: AWS-admitted workload lacks secret injection proof"
            )
        if row["kind"] == "service" and row["service_endpoints"] == "missing":
            failures.append(
                f"{workload}: AWS-admitted service lacks /health, /ready, or /metrics"
            )
        if row["kind"] == "service" and row["metrics_contract"] == "missing":
            failures.append(f"{workload}: AWS-admitted service lacks metrics contract")
        if row["kind"] == "job" and row["job_terminal_event"] == "missing":
            failures.append(
                f"{workload}: AWS-admitted job lacks terminal success event"
            )
        if row["kind"] == "job" and row["idempotency_contract"] == "missing":
            failures.append(f"{workload}: AWS-admitted job lacks idempotency contract")
        if row["eventing_contract"] == "missing":
            failures.append(f"{workload}: AWS-admitted eventing contract is incomplete")
    return failures


READINESS_VIEW_HEADERS = {
    "summary": [
        "workload",
        "kind",
        "class",
        "owner",
        "use_cases",
        "local_proof",
        "aws_ecs",
        "proof_surface",
        "proof_command",
    ],
    "local": [
        "workload",
        "kind",
        "class",
        "owner",
        "use_cases",
        "local_compose",
        "local_kubernetes",
        "local_kubernetes_admission",
        "service_endpoints",
        "logs_contract",
        "metrics_contract",
        "eventing_contract",
        "idempotency_contract",
        "job_terminal_event",
        "config_contract",
        "config_env",
        "config_realization",
        "secret_injection",
        "secret_names",
        "proof_surface",
    ],
    "aws": [
        "workload",
        "kind",
        "class",
        "owner",
        "use_cases",
        "aws_ecs_supported",
        "aws_ecs_admitted",
        "policy_delivery_gate",
        "build_matrix",
        "logs_contract",
        "metrics_contract",
        "eventing_contract",
        "idempotency_contract",
        "run_workflow",
        "evidence",
        "rollback_proof",
        "log_group",
        "config_contract",
        "config_env",
        "config_realization",
        "secret_injection",
        "secret_names",
    ],
    "all": [
        "workload",
        "kind",
        "class",
        "owner",
        "use_cases",
        "local_compose",
        "local_kubernetes",
        "aws_ecs_supported",
        "aws_ecs_admitted",
        "policy_delivery_gate",
        "local_kubernetes_admission",
        "proof_surface",
        "build_matrix",
        "service_endpoints",
        "logs_contract",
        "metrics_contract",
        "eventing_contract",
        "idempotency_contract",
        "job_terminal_event",
        "run_workflow",
        "evidence",
        "rollback_proof",
        "log_group",
        "config_contract",
        "config_env",
        "config_realization",
        "secret_injection",
        "secret_names",
    ],
    "addition": [
        "workload",
        "app_files",
        "uv_workspace",
        "dockerfile_copy",
        "compose_service",
        "runtime_conformance",
        "catalog_component",
        "app_tests",
    ],
}


def _local_proof_state(row: dict[str, str]) -> str:
    surfaces = []
    if row["local_compose"] == "yes":
        surfaces.append("local-compose")
    if row["local_kubernetes"] == "yes":
        surfaces.append(f"local-kubernetes:{row['local_kubernetes_admission']}")
    return "+".join(surfaces) if surfaces else "missing"


def _aws_ecs_state(row: dict[str, str]) -> str:
    if row["aws_ecs_admitted"] == "yes":
        return "admitted"
    if row["aws_ecs_supported"] == "yes":
        return "supported-not-admitted"
    return "not-supported"


def _proof_command(row: dict[str, str]) -> str:
    if row["aws_ecs_admitted"] == "yes":
        return "make platform-toolkit-validate-cloud"
    if row["local_kubernetes"] == "yes":
        if row["local_kubernetes_admission"] == "ready":
            return "make local-kubernetes-evidence-drill"
        return "make local-kubernetes-admission-report"
    if row["local_compose"] == "yes":
        return "make runtime-conformance"
    return "missing"


def _display_row(row: dict[str, str]) -> dict[str, str]:
    return {
        **row,
        "local_proof": _local_proof_state(row),
        "aws_ecs": _aws_ecs_state(row),
        "proof_command": _proof_command(row),
    }


def _print_table(rows: list[dict[str, str]], *, view: str) -> None:
    headers = READINESS_VIEW_HEADERS[view]
    print("\t".join(headers))
    for row in rows:
        display_row = _display_row(row)
        print("\t".join(display_row[header] for header in headers))


def _print_addition_table(rows: list[dict[str, str]]) -> None:
    headers = READINESS_VIEW_HEADERS["addition"]
    print("\t".join(headers))
    for row in rows:
        print("\t".join(row[header] for header in headers))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report workload paved-road readiness from platform contracts and conventional delivery files."
    )
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parser.add_argument(
        "--view",
        choices=sorted(READINESS_VIEW_HEADERS),
        default="summary",
        help="Choose the human table view. JSON output emits rows for the selected view.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when declared workloads are missing paved-road delivery surfaces.",
    )
    args = parser.parse_args()

    if args.view == "addition":
        rows = addition_rows()
        if args.format == "json":
            print(json.dumps(rows, sort_keys=True))
        else:
            _print_addition_table(rows)
        return 0

    rows = readiness_rows()
    if args.format == "json":
        print(json.dumps(rows, sort_keys=True))
    else:
        _print_table(rows, view=args.view)
    failures = readiness_failures(rows)
    if args.check and failures:
        print("\nReadiness check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
