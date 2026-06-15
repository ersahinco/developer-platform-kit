"""
verify_post_deploy.py — Check the primary edge workload after an ECS or local deploy.

The verifier always checks HTTP liveness, dependency readiness, Prometheus
metrics, and runtime read/write mode endpoints. If ECS_CLUSTER and ECS_SERVICE
are set, it also checks the active ECS task definition and primary edge image.

Usage:
    python -m scripts.release.verify_post_deploy

Environment:
    BASE_URL              Default: http://localhost:8000
    EXPECTED_READ_MODE    Optional: legacy | new
    EXPECTED_WRITE_MODE   Optional: legacy | dual | new
    ECS_CLUSTER           Optional ECS cluster name
    ECS_SERVICE           Optional ECS service name
    AWS_REGION            Default: eu-central-1
    EXPECTED_TASK_FAMILY  Optional task family, default: aws-sdlc-containers
    WORKLOAD_CONTAINER_NAME Optional container name for the primary edge workload
    EXPECTED_WORKLOAD_IMAGE Optional exact primary edge container image
    EXPECTED_IMAGE_TAG      Optional primary edge image tag, for example sha-<commit>
    TOKEN                 Optional bearer token for the public ALB
    AUTH_TOKEN            Optional bearer token alias
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from scripts.platform.workload_evidence import edge_service_repository
from scripts.platform.workload_read_model import primary_edge_contract


@dataclass
class CheckResult:
    ok: bool
    message: str


def _headers(accept: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if accept is not None:
        headers["Accept"] = accept
    token = os.environ.get("TOKEN") or os.environ.get("AUTH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _validated_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("BASE_URL must be an absolute http:// or https:// URL")
    return base_url.rstrip("/")


def _get_json(base_url: str, path: str) -> tuple[int, dict[str, Any]]:
    response = httpx.get(
        f"{_validated_base_url(base_url)}{path}",
        headers=_headers("application/json"),
        timeout=10,
    )
    return response.status_code, response.json()


def _get_text(base_url: str, path: str) -> tuple[int, str]:
    response = httpx.get(
        f"{_validated_base_url(base_url)}{path}",
        headers=_headers(),
        timeout=10,
    )
    return response.status_code, response.text


def _check_http(base_url: str) -> list[CheckResult]:
    results: list[CheckResult] = []
    edge_contract = primary_edge_contract()
    required_metrics = edge_contract["metrics_required_names"]

    try:
        status_code, health = _get_json(base_url, "/health")
        results.append(
            CheckResult(
                status_code == 200 and health.get("status") == "ok",
                f"/health returned {status_code} with status={health.get('status')!r}",
            )
        )
    except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
        results.append(CheckResult(False, f"/health request failed: {exc}"))

    try:
        status_code, ready = _get_json(base_url, "/ready")
        checks = ready.get("checks", {})
        results.append(
            CheckResult(
                status_code == 200
                and ready.get("status") == "ready"
                and checks.get("database") == "ok",
                f"/ready returned {status_code} with status={ready.get('status')!r} database={checks.get('database')!r}",
            )
        )
    except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
        results.append(CheckResult(False, f"/ready request failed: {exc}"))

    try:
        status_code, metrics = _get_text(base_url, "/metrics")
        missing_metrics = [
            metric_name
            for metric_name in required_metrics
            if metric_name not in metrics
        ]
        results.append(
            CheckResult(
                status_code == 200 and not missing_metrics,
                f"/metrics returned {status_code} missing_metrics={missing_metrics}",
            )
        )
    except (httpx.HTTPError, ValueError) as exc:
        results.append(CheckResult(False, f"/metrics request failed: {exc}"))

    return results


def _check_runtime_mode(
    base_url: str, path: str, expected: str | None, label: str
) -> CheckResult:
    try:
        status_code, response = _get_json(base_url, path)
    except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
        return CheckResult(False, f"{path} request failed: {exc}")

    mode = response.get("mode")
    if expected is None:
        return CheckResult(
            status_code == 200 and isinstance(mode, str),
            f"{label} mode is {mode!r}",
        )

    return CheckResult(
        status_code == 200 and mode == expected,
        f"{label} mode is {mode!r}, expected {expected!r}",
    )


def _runtime_mode_checks(base_url: str) -> list[CheckResult]:
    runtime_mode_endpoints = primary_edge_contract()["runtime_mode_endpoints"]
    if not runtime_mode_endpoints:
        return [CheckResult(True, "runtime-mode checks skipped; no endpoints declared")]

    results: list[CheckResult] = []
    read_endpoint = runtime_mode_endpoints.get("read")
    write_endpoint = runtime_mode_endpoints.get("write")

    if read_endpoint is not None:
        results.append(
            _check_runtime_mode(
                base_url,
                read_endpoint,
                os.environ.get("EXPECTED_READ_MODE"),
                "READ_MODE",
            )
        )
    if write_endpoint is not None:
        results.append(
            _check_runtime_mode(
                base_url,
                write_endpoint,
                os.environ.get("EXPECTED_WRITE_MODE"),
                "WRITE_MODE",
            )
        )
    return results


def _aws_json(args: list[str], region: str) -> dict[str, Any]:
    command = ["aws", *args, "--region", region, "--output", "json"]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def _describe_ecs_service(
    cluster: str, service_name: str, region: str
) -> dict[str, Any]:
    service_response = _aws_json(
        [
            "ecs",
            "describe-services",
            "--cluster",
            cluster,
            "--services",
            service_name,
        ],
        region,
    )
    services = service_response.get("services", [])
    if not services:
        raise KeyError(f"ECS service {service_name!r} was not found")
    return services[0]


def _primary_deployment(service: dict[str, Any]) -> dict[str, Any]:
    return next(
        deployment
        for deployment in service.get("deployments", [])
        if deployment.get("status") == "PRIMARY"
    )


def _wait_for_ecs_primary_rollout(
    cluster: str, service_name: str, region: str
) -> dict[str, Any]:
    timeout_seconds = int(os.environ.get("ECS_ROLLOUT_WAIT_SECONDS", "120"))
    poll_seconds = int(os.environ.get("ECS_ROLLOUT_POLL_SECONDS", "5"))
    deadline = time.monotonic() + timeout_seconds

    while True:
        service = _describe_ecs_service(cluster, service_name, region)
        primary = _primary_deployment(service)
        if (
            service.get("runningCount") == service.get("desiredCount")
            and primary.get("rolloutState") == "COMPLETED"
        ):
            return service
        if time.monotonic() >= deadline:
            return service
        time.sleep(poll_seconds)


def _check_ecs() -> list[CheckResult]:
    cluster = os.environ.get("ECS_CLUSTER")
    service_name = os.environ.get("ECS_SERVICE")
    if not cluster and not service_name:
        return [
            CheckResult(
                True, "ECS checks skipped; ECS_CLUSTER and ECS_SERVICE are not set"
            )
        ]
    if not cluster or not service_name:
        return [CheckResult(False, "ECS_CLUSTER and ECS_SERVICE must be set together")]

    region = os.environ.get("AWS_REGION", "eu-central-1")
    expected_family = (
        os.environ.get("EXPECTED_TASK_FAMILY")
        or os.environ.get("STACK_NAME")
        or cluster
        or "aws-sdlc-containers"
    )
    workload_container_name = os.environ.get(
        "WORKLOAD_CONTAINER_NAME", edge_service_repository()
    )
    expected_image = os.environ.get("EXPECTED_WORKLOAD_IMAGE")
    expected_tag = os.environ.get("EXPECTED_IMAGE_TAG")

    try:
        service = _wait_for_ecs_primary_rollout(cluster, service_name, region)
        task_definition_arn = service["taskDefinition"]
        primary = _primary_deployment(service)

        task_response = _aws_json(
            [
                "ecs",
                "describe-task-definition",
                "--task-definition",
                task_definition_arn,
            ],
            region,
        )
    except (
        KeyError,
        StopIteration,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
    ) as exc:
        return [CheckResult(False, f"ECS metadata check failed: {exc}")]

    task_definition = task_response["taskDefinition"]
    containers = task_definition.get("containerDefinitions", [])
    workload_container = next(
        (
            container
            for container in containers
            if container.get("name") == workload_container_name
        ),
        None,
    )
    workload_image = workload_container.get("image") if workload_container else None

    results = [
        CheckResult(
            service.get("runningCount") == service.get("desiredCount"),
            f"ECS service runningCount={service.get('runningCount')} desiredCount={service.get('desiredCount')}",
        ),
        CheckResult(
            primary.get("rolloutState") == "COMPLETED",
            f"ECS primary deployment rolloutState={primary.get('rolloutState')!r}",
        ),
        CheckResult(
            task_definition.get("family") == expected_family,
            f"ECS task family={task_definition.get('family')!r}, expected {expected_family!r}",
        ),
        CheckResult(
            workload_container is not None,
            f"ECS workload container {workload_container_name!r} is present",
        ),
    ]

    if expected_image is not None:
        results.append(
            CheckResult(
                workload_image == expected_image,
                f"ECS workload image={workload_image!r}, expected {expected_image!r}",
            )
        )
    if expected_tag is not None:
        results.append(
            CheckResult(
                isinstance(workload_image, str)
                and workload_image.endswith(f":{expected_tag}"),
                f"ECS workload image={workload_image!r}, expected tag {expected_tag!r}",
            )
        )

    return results


def main() -> int:
    base_url = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
    results = [
        *_check_http(base_url),
        *_runtime_mode_checks(base_url),
        *_check_ecs(),
    ]

    for result in results:
        prefix = "OK" if result.ok else "FAIL"
        stream = sys.stdout if result.ok else sys.stderr
        print(f"{prefix}: {result.message}", file=stream)

    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
