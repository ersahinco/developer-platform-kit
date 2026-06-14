from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from scripts.platform.local_kubernetes.constants import API_METRIC_NEEDLE
from scripts.platform.local_kubernetes.constants import DEFAULT_NAMESPACE
from scripts.platform.local_kubernetes.constants import DEFAULT_OUTPUT_DIR
from scripts.platform.local_kubernetes.evidence import write_evidence
from scripts.platform.local_kubernetes.runner import CommandResult
from scripts.platform.local_kubernetes.runner import CommandRunner
from scripts.platform.local_kubernetes.runner import ProofError
from scripts.platform.local_kubernetes.runner import checked
from scripts.platform.local_kubernetes.runner import run_command


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
        _append_step(steps, name, result)
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
    return write_evidence(evidence, output_dir, "local-kubernetes-rollout-proof")


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
    _append_step(steps, name, result)


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
    _append_step(steps, name, result)


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
    _append_step(steps, name, result)


def _append_step(
    steps: list[dict[str, Any]],
    name: str,
    result: CommandResult,
) -> None:
    steps.append({"name": name, **asdict(result)})
