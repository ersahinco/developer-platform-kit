from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from scripts.platform.local_kubernetes.constants import DEFAULT_NAMESPACE
from scripts.platform.local_kubernetes.constants import DEFAULT_OUTPUT_DIR
from scripts.platform.local_kubernetes.constants import EVENT_CONSUMED_NEEDLE
from scripts.platform.local_kubernetes.constants import EVENT_CONSUMER_METRIC_NEEDLE
from scripts.platform.local_kubernetes.evidence import write_evidence
from scripts.platform.local_kubernetes.rollout import _append_step
from scripts.platform.local_kubernetes.rollout import _record_ready_pods
from scripts.platform.local_kubernetes.rollout import _record_service_endpoints
from scripts.platform.local_kubernetes.runner import CommandResult
from scripts.platform.local_kubernetes.runner import CommandRunner
from scripts.platform.local_kubernetes.runner import ProofError
from scripts.platform.local_kubernetes.runner import checked
from scripts.platform.local_kubernetes.runner import run_command

import time


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
        _append_step(steps, name, result)
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
    _append_step(steps, "event_consumed_logs", logs)

    evidence = {
        "runtime_target": "local-kubernetes",
        "namespace": namespace,
        "status": "succeeded",
        "workload": "event_consumer",
        "order_id": order_id,
        "steps": steps,
    }
    return write_evidence(evidence, output_dir, "local-kubernetes-dapr-eventing-proof")


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
    _append_step(steps, name, result)


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
