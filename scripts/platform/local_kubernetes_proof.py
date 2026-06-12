#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import time
from typing import Any, Callable

import yaml


ROOT = Path(__file__).resolve().parents[2]
LOCAL_KUBERNETES_ROOT = ROOT / "infra" / "local-kubernetes"
DEFAULT_NAMESPACE = "aws-sdlc-local"
DEFAULT_OUTPUT_DIR = Path("/tmp/aws-sdlc-containers-local-kubernetes-evidence")
API_METRIC_NEEDLE = 'workload_info{workload="api"'
EVENT_CONSUMER_METRIC_NEEDLE = 'workload_info{workload="event_consumer"'
EVENT_CONSUMED_NEEDLE = '"event": "event_consumed"'


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class AdmissionRow:
    workload: str
    kind: str
    status: str
    supported: bool
    manifest: str
    checks: list[str]
    blockers: list[str]


CommandRunner = Callable[[list[str]], CommandResult]


class ProofError(RuntimeError):
    pass


def run_command(command: list[str]) -> CommandResult:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return CommandResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def checked(command: list[str], runner: CommandRunner = run_command) -> CommandResult:
    result = runner(command)
    if result.returncode != 0:
        raise ProofError(
            "command failed: "
            + " ".join(command)
            + f"\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _load_json(path: str) -> dict[str, Any]:
    data = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _documents() -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for path in sorted(LOCAL_KUBERNETES_ROOT.glob("*.yaml")):
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if isinstance(document, dict):
                documents.append(document)
    return documents


def _metadata(document: dict[str, Any]) -> dict[str, Any]:
    metadata = document.get("metadata", {})
    return metadata if isinstance(metadata, dict) else {}


def _workload_label(document: dict[str, Any]) -> str | None:
    template = document.get("spec", {}).get("template", {})
    metadata = template.get("metadata", {}) if isinstance(template, dict) else {}
    labels = metadata.get("labels", {}) if isinstance(metadata, dict) else {}
    workload = labels.get("workload") if isinstance(labels, dict) else None
    return workload if isinstance(workload, str) else None


def _document_name(document: dict[str, Any]) -> str:
    name = _metadata(document).get("name", "")
    return str(name)


def _document_by_kind_name() -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(document.get("kind")), _document_name(document)): document
        for document in _documents()
    }


def _workload_manifest(workload: dict[str, Any]) -> dict[str, Any] | None:
    expected_kind = "Deployment" if workload["kind"] == "service" else "Job"
    for document in _documents():
        if (
            document.get("kind") == expected_kind
            and _workload_label(document) == workload["name"]
        ):
            return document
    return None


def _config_names(workload: dict[str, Any]) -> set[str]:
    config = workload["config"]
    return set(config["env"]) | set(config["secrets"])


def admission_rows() -> list[AdmissionRow]:
    workloads = _load_json("platform/workloads.json")["workloads"]
    documents = _document_by_kind_name()
    config_map = documents.get(("ConfigMap", "workload-config"), {})
    secret = documents.get(("Secret", "workload-secrets"), {})
    config_names = set(config_map.get("data", {}))
    secret_names = set(secret.get("stringData", {}))
    available_config = config_names | secret_names
    rows: list[AdmissionRow] = []

    for workload in workloads:
        supported = "local-kubernetes" in workload["runtime"]["supported"]
        manifest = _workload_manifest(workload)
        checks: list[str] = []
        blockers: list[str] = []

        if not supported:
            blockers.append("runtime.supported does not include local-kubernetes")
        if manifest is None:
            blockers.append("no local Kubernetes Deployment/Job manifest")
            manifest_name = ""
        else:
            manifest_name = f"{manifest['kind']}/{_document_name(manifest)}"
            checks.append(manifest_name)

        if supported or manifest is not None:
            missing_config = sorted(_config_names(workload) - available_config)
            if missing_config:
                blockers.append(
                    "missing local config or secret names: " + ", ".join(missing_config)
                )
            elif supported:
                checks.append("config and secret names are injectable")

            if workload["kind"] == "service":
                service = documents.get(("Service", _document_name(manifest or {})))
                container = _first_container(manifest)
                if service is None:
                    blockers.append("no matching local Kubernetes Service")
                elif supported:
                    checks.append(f"Service/{_document_name(service)}")
                if not _has_http_probe(container, "readinessProbe", "/ready"):
                    blockers.append("service lacks /ready readinessProbe")
                if not _has_http_probe(container, "livenessProbe", "/health"):
                    blockers.append("service lacks /health livenessProbe")
                if container and supported:
                    checks.append("health and readiness probes")
            else:
                spec = manifest.get("spec", {}) if isinstance(manifest, dict) else {}
                template_spec = spec.get("template", {}).get("spec", {})
                if template_spec.get("restartPolicy") != "Never":
                    blockers.append("job restartPolicy must be Never")
                if "backoffLimit" not in spec:
                    blockers.append("job backoffLimit is not explicit")
                if supported and template_spec.get("restartPolicy") == "Never":
                    checks.append("bounded job execution")

        if workload.get("dapr"):
            if not _has_local_dapr_eventing(documents, manifest):
                blockers.append("local Kubernetes Dapr/eventing proof is not present")
            elif supported:
                checks.append("Dapr pub/sub sidecar and Redis proof path")

        status = "ready" if supported and not blockers else "not-ready"
        rows.append(
            AdmissionRow(
                workload=workload["name"],
                kind=workload["kind"],
                status=status,
                supported=supported,
                manifest=manifest_name,
                checks=checks,
                blockers=blockers,
            )
        )
    return rows


def _first_container(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(document, dict):
        return None
    containers = (
        document.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("containers", [])
    )
    if isinstance(containers, list) and containers:
        container = containers[0]
        return container if isinstance(container, dict) else None
    return None


def _has_http_probe(container: dict[str, Any] | None, probe: str, path: str) -> bool:
    if not isinstance(container, dict):
        return False
    http_get = container.get(probe, {}).get("httpGet", {})
    return isinstance(http_get, dict) and http_get.get("path") == path


def _has_local_dapr_eventing(
    documents: dict[tuple[str, str], dict[str, Any]],
    manifest: dict[str, Any] | None,
) -> bool:
    if not isinstance(manifest, dict):
        return False
    containers = (
        manifest.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("containers", [])
    )
    container_names = {
        container.get("name") for container in containers if isinstance(container, dict)
    }
    return (
        "event-consumer" in container_names
        and "daprd" in container_names
        and ("ConfigMap", "dapr-components") in documents
        and ("ConfigMap", "dapr-config") in documents
        and ("Deployment", "redis") in documents
        and ("Service", "redis") in documents
    )


def collect_evidence_bundle(
    *,
    namespace: str = DEFAULT_NAMESPACE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    runner: CommandRunner = run_command,
) -> dict[str, Any]:
    commands = {
        "pods": ["kubectl", "-n", namespace, "get", "pods", "-o", "wide"],
        "deployments": ["kubectl", "-n", namespace, "get", "deployments", "-o", "wide"],
        "services": ["kubectl", "-n", namespace, "get", "services", "-o", "wide"],
        "jobs": ["kubectl", "-n", namespace, "get", "jobs", "-o", "wide"],
        "endpoints": ["kubectl", "-n", namespace, "get", "endpoints", "-o", "wide"],
        "events": [
            "kubectl",
            "-n",
            namespace,
            "get",
            "events",
            "--sort-by=.lastTimestamp",
        ],
        "api_rollout": [
            "kubectl",
            "-n",
            namespace,
            "rollout",
            "status",
            "deployment/api",
            "--timeout=30s",
        ],
        "api_describe": ["kubectl", "-n", namespace, "describe", "deployment/api"],
        "api_logs": [
            "kubectl",
            "-n",
            namespace,
            "logs",
            "deployment/api",
            "--tail=120",
        ],
        "event_consumer_describe": [
            "kubectl",
            "-n",
            namespace,
            "describe",
            "deployment/event-consumer",
        ],
        "event_consumer_logs": [
            "kubectl",
            "-n",
            namespace,
            "logs",
            "deployment/event-consumer",
            "-c",
            "event-consumer",
            "--tail=160",
        ],
        "event_consumer_daprd_logs": [
            "kubectl",
            "-n",
            namespace,
            "logs",
            "deployment/event-consumer",
            "-c",
            "daprd",
            "--tail=160",
        ],
        "redis_logs": [
            "kubectl",
            "-n",
            namespace,
            "logs",
            "deployment/redis",
            "--tail=120",
        ],
        "backfill_logs": [
            "kubectl",
            "-n",
            namespace,
            "logs",
            "job/backfill-worker",
            "--tail=120",
        ],
        "data_export_logs": [
            "kubectl",
            "-n",
            namespace,
            "logs",
            "job/data-export-job",
            "--tail=120",
        ],
        "integration_check_logs": [
            "kubectl",
            "-n",
            namespace,
            "logs",
            "job/integration-check-job",
            "--tail=120",
        ],
        "operational_snapshot_logs": [
            "kubectl",
            "-n",
            namespace,
            "logs",
            "job/operational-snapshot-job",
            "--tail=120",
        ],
    }
    results = {name: asdict(runner(command)) for name, command in commands.items()}
    status = (
        "succeeded"
        if all(result["returncode"] == 0 for result in results.values())
        else "failed"
    )
    evidence = {
        "runtime_target": "local-kubernetes",
        "namespace": namespace,
        "status": status,
        "commands": results,
        "admission": [asdict(row) for row in admission_rows()],
    }
    return _write_evidence(evidence, output_dir, "local-kubernetes-evidence")


def dapr_eventing_proof(
    *,
    namespace: str = DEFAULT_NAMESPACE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    runner: CommandRunner = run_command,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []

    def record(name: str, command: list[str]) -> CommandResult:
        result = checked(command, runner)
        steps.append({"name": name, **asdict(result)})
        return result

    record(
        "api_rollout_status",
        [
            "kubectl",
            "-n",
            namespace,
            "rollout",
            "status",
            "deployment/api",
            "--timeout=180s",
        ],
    )
    _record_ready_pods(namespace, "api", "api_ready_pods", steps, runner)
    _record_service_endpoints(namespace, "api", "api_service_endpoints", steps, runner)
    record(
        "event_consumer_rollout_status",
        [
            "kubectl",
            "-n",
            namespace,
            "rollout",
            "status",
            "deployment/event-consumer",
            "--timeout=180s",
        ],
    )
    _record_ready_pods(
        namespace, "event-consumer", "event_consumer_ready_pods", steps, runner
    )
    _record_service_endpoints(
        namespace, "event-consumer", "event_consumer_service_endpoints", steps, runner
    )
    _record_service_endpoints(
        namespace, "redis", "redis_service_endpoints", steps, runner
    )
    _record_event_consumer_probe(
        namespace, "event_consumer_health", "/health", steps, runner
    )
    _record_event_consumer_probe(
        namespace, "event_consumer_ready", "/ready", steps, runner
    )
    _record_event_consumer_probe(
        namespace,
        "event_consumer_metrics",
        "/metrics",
        steps,
        runner,
        EVENT_CONSUMER_METRIC_NEEDLE,
    )
    record(
        "seed_eventing_customer",
        [
            "kubectl",
            "-n",
            namespace,
            "run",
            "seed-eventing-customer",
            "--rm",
            "-i",
            "--restart=Never",
            "--image=postgres:18.3",
            "--env",
            "PGPASSWORD=postgres",
            "--command",
            "--",
            "psql",
            "-h",
            "db",
            "-U",
            "postgres",
            "-d",
            "aws_sdlc_containers",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            "INSERT INTO customers (id, name, created_at) VALUES "
            "(1, 'Local Kubernetes Dapr Proof', now()) ON CONFLICT (id) DO NOTHING",
        ],
    )
    order = record(
        "create_order_for_eventing",
        [
            "kubectl",
            "-n",
            namespace,
            "run",
            "api-order-eventing-proof",
            "--rm",
            "-i",
            "--restart=Never",
            "--image=curlimages/curl:8.17.0",
            "--command",
            "--",
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--connect-timeout",
            "2",
            "--max-time",
            "10",
            "--retry",
            "6",
            "--retry-delay",
            "2",
            "--retry-connrefused",
            "-X",
            "POST",
            "http://api:8000/orders",
            "-H",
            "Content-Type: application/json",
            "-H",
            "Idempotency-Key: local-kubernetes-dapr-proof",
            "-d",
            '{"customer_id":1,"total_amount":"42.00","billing_email":"local-kubernetes-dapr@example.com"}',
        ],
    )
    order_id = _extract_json_field(order.stdout, "id")
    if order_id is None:
        raise ProofError("eventing proof order response did not include id")

    logs = _wait_for_log_text(
        [
            "kubectl",
            "-n",
            namespace,
            "logs",
            "deployment/event-consumer",
            "-c",
            "event-consumer",
            "--tail=240",
        ],
        EVENT_CONSUMED_NEEDLE,
        runner=runner,
        monotonic=monotonic,
        sleep=sleep,
    )
    steps.append({"name": "event_consumed_logs", **asdict(logs)})

    evidence = {
        "runtime_target": "local-kubernetes",
        "namespace": namespace,
        "status": "succeeded",
        "workload": "event_consumer",
        "order_id": order_id,
        "steps": steps,
    }
    return _write_evidence(evidence, output_dir, "local-kubernetes-dapr-eventing-proof")


def rollout_rollback_proof(
    *,
    namespace: str = DEFAULT_NAMESPACE,
    deployment: str = "api",
    container: str = "api",
    candidate_image: str,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    runner: CommandRunner = run_command,
) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []

    def record(name: str, command: list[str]) -> CommandResult:
        result = checked(command, runner)
        steps.append({"name": name, **asdict(result)})
        return result

    current_image = record(
        "current_image",
        [
            "kubectl",
            "-n",
            namespace,
            "get",
            f"deployment/{deployment}",
            "-o",
            f'jsonpath={{.spec.template.spec.containers[?(@.name=="{container}")].image}}',
        ],
    ).stdout.strip()
    record(
        "initial_rollout_status",
        [
            "kubectl",
            "-n",
            namespace,
            "rollout",
            "status",
            f"deployment/{deployment}",
            "--timeout=180s",
        ],
    )
    _record_ready_pods(namespace, deployment, "initial_ready_pods", steps, runner)
    _record_service_endpoints(
        namespace, deployment, "initial_service_endpoints", steps, runner
    )
    _record_api_probe(namespace, "initial_health", "/health", steps, runner)
    _record_api_probe(namespace, "initial_ready", "/ready", steps, runner)
    _record_api_probe(
        namespace, "initial_metrics", "/metrics", steps, runner, API_METRIC_NEEDLE
    )

    try:
        record(
            "set_candidate_image",
            [
                "kubectl",
                "-n",
                namespace,
                "set",
                "image",
                f"deployment/{deployment}",
                f"{container}={candidate_image}",
            ],
        )
        record(
            "candidate_rollout_status",
            [
                "kubectl",
                "-n",
                namespace,
                "rollout",
                "status",
                f"deployment/{deployment}",
                "--timeout=180s",
            ],
        )
        _record_ready_pods(namespace, deployment, "candidate_ready_pods", steps, runner)
        _record_service_endpoints(
            namespace, deployment, "candidate_service_endpoints", steps, runner
        )
        _record_api_probe(namespace, "candidate_health", "/health", steps, runner)
        _record_api_probe(namespace, "candidate_ready", "/ready", steps, runner)
        _record_api_probe(
            namespace, "candidate_metrics", "/metrics", steps, runner, API_METRIC_NEEDLE
        )
    finally:
        record(
            "rollback",
            ["kubectl", "-n", namespace, "rollout", "undo", f"deployment/{deployment}"],
        )
        record(
            "rollback_rollout_status",
            [
                "kubectl",
                "-n",
                namespace,
                "rollout",
                "status",
                f"deployment/{deployment}",
                "--timeout=180s",
            ],
        )

    _record_ready_pods(namespace, deployment, "rollback_ready_pods", steps, runner)
    _record_service_endpoints(
        namespace, deployment, "rollback_service_endpoints", steps, runner
    )
    _record_api_probe(namespace, "rollback_health", "/health", steps, runner)
    _record_api_probe(namespace, "rollback_ready", "/ready", steps, runner)
    _record_api_probe(
        namespace, "rollback_metrics", "/metrics", steps, runner, API_METRIC_NEEDLE
    )

    evidence = {
        "runtime_target": "local-kubernetes",
        "namespace": namespace,
        "status": "succeeded",
        "deployment": deployment,
        "container": container,
        "initial_image": current_image,
        "candidate_image": candidate_image,
        "steps": steps,
    }
    return _write_evidence(evidence, output_dir, "local-kubernetes-rollout-proof")


def _record_ready_pods(
    namespace: str,
    app_name: str,
    name: str,
    steps: list[dict[str, Any]],
    runner: CommandRunner,
) -> None:
    command = [
        "kubectl",
        "-n",
        namespace,
        "wait",
        "--for=condition=ready",
        "pod",
        "-l",
        f"app.kubernetes.io/name={app_name}",
        "--timeout=180s",
    ]
    result = checked(command, runner)
    steps.append({"name": name, **asdict(result)})


def _record_service_endpoints(
    namespace: str,
    service: str,
    name: str,
    steps: list[dict[str, Any]],
    runner: CommandRunner,
) -> None:
    command = [
        "kubectl",
        "-n",
        namespace,
        "get",
        "endpoints",
        service,
        "-o",
        "jsonpath={.subsets[*].addresses[*].ip}",
    ]
    result = checked(command, runner)
    if not result.stdout.strip():
        raise ProofError(f"{service} service has no ready endpoints")
    steps.append({"name": name, **asdict(result)})


def _record_api_probe(
    namespace: str,
    name: str,
    path: str,
    steps: list[dict[str, Any]],
    runner: CommandRunner,
    required_text: str | None = None,
) -> None:
    probe_name = "api-probe-" + name.replace("_", "-")
    command = [
        "kubectl",
        "-n",
        namespace,
        "run",
        probe_name,
        "--rm",
        "-i",
        "--restart=Never",
        "--image=curlimages/curl:8.17.0",
        "--command",
        "--",
        "curl",
        "--fail",
        "--silent",
        "--show-error",
        "--connect-timeout",
        "2",
        "--max-time",
        "5",
        "--retry",
        "12",
        "--retry-delay",
        "2",
        "--retry-connrefused",
        f"http://api:8000{path}",
    ]
    result = checked(command, runner)
    if required_text is not None and required_text not in result.stdout:
        raise ProofError(f"{name} response did not contain {required_text!r}")
    steps.append({"name": name, **asdict(result)})


def _record_event_consumer_probe(
    namespace: str,
    name: str,
    path: str,
    steps: list[dict[str, Any]],
    runner: CommandRunner,
    required_text: str | None = None,
) -> None:
    probe_name = "event-consumer-probe-" + name.replace("_", "-")
    command = [
        "kubectl",
        "-n",
        namespace,
        "run",
        probe_name,
        "--rm",
        "-i",
        "--restart=Never",
        "--image=curlimages/curl:8.17.0",
        "--command",
        "--",
        "curl",
        "--fail",
        "--silent",
        "--show-error",
        "--connect-timeout",
        "2",
        "--max-time",
        "5",
        "--retry",
        "12",
        "--retry-delay",
        "2",
        "--retry-connrefused",
        f"http://event-consumer:8081{path}",
    ]
    result = checked(command, runner)
    if required_text is not None and required_text not in result.stdout:
        raise ProofError(f"{name} response did not contain {required_text!r}")
    steps.append({"name": name, **asdict(result)})


def _wait_for_log_text(
    command: list[str],
    required_text: str,
    *,
    runner: CommandRunner,
    monotonic: Callable[[], float],
    sleep: Callable[[float], None],
    timeout_seconds: float = 90,
    interval_seconds: float = 3,
) -> CommandResult:
    deadline = monotonic() + timeout_seconds
    last_result = CommandResult(command=command, returncode=1, stdout="", stderr="")
    while monotonic() < deadline:
        result = runner(command)
        last_result = result
        if result.returncode == 0 and required_text in result.stdout:
            return result
        sleep(interval_seconds)
    raise ProofError(
        "log text not observed: "
        + required_text
        + f"\nstdout:\n{last_result.stdout}\nstderr:\n{last_result.stderr}"
    )


def _extract_json_field(output: str, field: str) -> object | None:
    start = output.find("{")
    end = output.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        value = json.loads(output[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    return value.get(field)


def _write_evidence(
    evidence: dict[str, Any],
    output_dir: Path,
    stem: str,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    evidence = {
        **evidence,
        "evidence_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    json_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(_markdown(evidence), encoding="utf-8")
    return evidence


def _markdown(evidence: dict[str, Any]) -> str:
    lines = [
        "# Local Kubernetes Evidence",
        "",
        f"- runtime_target: `{evidence['runtime_target']}`",
        f"- namespace: `{evidence['namespace']}`",
        f"- status: `{evidence['status']}`",
    ]
    if "candidate_image" in evidence:
        lines.extend(
            [
                f"- initial_image: `{evidence['initial_image']}`",
                f"- candidate_image: `{evidence['candidate_image']}`",
            ]
        )
    lines.append("")
    if "steps" in evidence:
        lines.append("## Rollout Steps")
        for step in evidence["steps"]:
            lines.append(f"- `{step['name']}`: exit `{step['returncode']}`")
    if "commands" in evidence:
        lines.append("## Captured Commands")
        for name, result in evidence["commands"].items():
            lines.append(f"- `{name}`: exit `{result['returncode']}`")
    if "admission" in evidence:
        lines.append("## Admission")
        for row in evidence["admission"]:
            blockers = "; ".join(row["blockers"]) if row["blockers"] else "none"
            lines.append(
                f"- `{row['workload']}`: `{row['status']}`; blockers: {blockers}"
            )
    lines.append("")
    return "\n".join(lines)


def _print_admission(rows: list[AdmissionRow], *, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps([asdict(row) for row in rows], indent=2, sort_keys=True))
        return
    print("\t".join(["workload", "kind", "status", "manifest", "blockers"]))
    for row in rows:
        blockers = "; ".join(row.blockers) if row.blockers else "-"
        print(
            "\t".join(
                [row.workload, row.kind, row.status, row.manifest or "-", blockers]
            )
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Local Kubernetes rollout, evidence, and admission proof helpers."
    )
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    subparsers = parser.add_subparsers(dest="command", required=True)

    rollout = subparsers.add_parser("rollout-proof")
    rollout.add_argument("--deployment", default="api")
    rollout.add_argument("--container", default="api")
    rollout.add_argument("--candidate-image", required=True)

    subparsers.add_parser("dapr-eventing-proof")

    subparsers.add_parser("evidence-bundle")

    admission = subparsers.add_parser("admission-report")
    admission.add_argument("--format", choices=["table", "json"], default="table")

    args = parser.parse_args(argv)

    if args.command == "rollout-proof":
        evidence = rollout_rollback_proof(
            namespace=args.namespace,
            deployment=args.deployment,
            container=args.container,
            candidate_image=args.candidate_image,
            output_dir=args.output_dir,
        )
        print(f"wrote {evidence['evidence_path']}")
        print(f"wrote {evidence['markdown_path']}")
        return 0
    if args.command == "evidence-bundle":
        evidence = collect_evidence_bundle(
            namespace=args.namespace, output_dir=args.output_dir
        )
        print(f"wrote {evidence['evidence_path']}")
        print(f"wrote {evidence['markdown_path']}")
        return 0 if evidence["status"] == "succeeded" else 1
    if args.command == "dapr-eventing-proof":
        evidence = dapr_eventing_proof(
            namespace=args.namespace,
            output_dir=args.output_dir,
        )
        print(f"wrote {evidence['evidence_path']}")
        print(f"wrote {evidence['markdown_path']}")
        return 0
    if args.command == "admission-report":
        _print_admission(admission_rows(), output_format=args.format)
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
