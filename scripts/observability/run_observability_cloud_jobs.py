"""
run_observability_cloud_jobs.py — Exercise quiet cloud log producers.

This complements API traffic with a few bounded ECS actions so Loki/CloudWatch
receive post-roll log lines from batch and quiet daemon groups.

Environment:
    AWS_REGION                         Default: eu-central-1
    STACK_NAME                         Default: aws-sdlc-containers
    ECS_CLUSTER                        Default: STACK_NAME
    OBSERVABILITY_CLOUD_JOB_TARGETS    Default: worker,data-export-job,liquibase,prometheus,tempo
    OBSERVABILITY_RESTART_QUIET_DAEMONS
                                       Default: true
    BACKFILL_MAX_BATCHES               Default: 1 for the worker probe
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class ProbeResult:
    ok: bool
    label: str
    detail: str


@dataclass(frozen=True)
class NetworkConfig:
    subnet_id: str
    security_group_id: str


BATCH_TARGETS = {"worker", "data-export-job", "liquibase"}
DAEMON_TARGETS = {"prometheus", "tempo"}
DEFAULT_TARGETS = ["worker", "data-export-job", "liquibase", "prometheus", "tempo"]


def _csv_env(name: str, default: list[str]) -> list[str]:
    value = os.environ.get(name)
    if value is None:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _run(command: list[str], *, cwd: str | None = None) -> str:
    result = subprocess.run(
        command,
        check=True,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.stdout


def _aws_json(args: list[str], region: str) -> dict[str, Any]:
    return json.loads(_run(["aws", *args, "--region", region, "--output", "json"]))


def _resolve_network(stack_name: str, region: str) -> NetworkConfig:
    subnets = _aws_json(
        [
            "ec2",
            "describe-subnets",
            "--filters",
            f"Name=tag:Name,Values={stack_name}-private-*",
        ],
        region,
    ).get("Subnets", [])
    security_groups = _aws_json(
        [
            "ec2",
            "describe-security-groups",
            "--filters",
            f"Name=group-name,Values={stack_name}-app-*",
        ],
        region,
    ).get("SecurityGroups", [])

    subnet_id = next(
        (
            subnet.get("SubnetId")
            for subnet in subnets
            if isinstance(subnet.get("SubnetId"), str)
        ),
        None,
    )
    security_group_id = next(
        (
            group.get("GroupId")
            for group in security_groups
            if isinstance(group.get("GroupId"), str)
        ),
        None,
    )
    if not subnet_id or not security_group_id:
        raise RuntimeError(
            f"Could not resolve private subnet/security group for stack {stack_name}"
        )
    return NetworkConfig(subnet_id=subnet_id, security_group_id=security_group_id)


def _task_definition(stack_name: str, target: str) -> str:
    return f"{stack_name}-{target}"


def _run_task(
    *,
    cluster: str,
    task_definition: str,
    container_name: str,
    network: NetworkConfig,
    region: str,
    overrides: dict[str, Any] | None = None,
) -> str:
    command = [
        "aws",
        "ecs",
        "run-task",
        "--cluster",
        cluster,
        "--task-definition",
        task_definition,
        "--launch-type",
        "FARGATE",
        "--network-configuration",
        (
            "awsvpcConfiguration={"
            f"subnets=[{network.subnet_id}],"
            f"securityGroups=[{network.security_group_id}],"
            "assignPublicIp=DISABLED}"
        ),
    ]
    if overrides:
        command.extend(["--overrides", json.dumps(overrides, separators=(",", ":"))])

    response = _aws_json(command[1:], region)
    failures = response.get("failures", [])
    if failures:
        raise RuntimeError(f"ECS run-task failed for {task_definition}: {failures}")

    tasks = response.get("tasks", [])
    task_arn = tasks[0].get("taskArn") if tasks else None
    if not isinstance(task_arn, str):
        raise RuntimeError(f"ECS run-task did not start {task_definition}")
    print(f"Started {container_name}: {task_arn}", flush=True)
    return task_arn


def _wait_task_stopped(cluster: str, task_arn: str, region: str, label: str) -> None:
    while True:
        response = _aws_json(
            ["ecs", "describe-tasks", "--cluster", cluster, "--tasks", task_arn],
            region,
        )
        tasks = response.get("tasks", [])
        status = tasks[0].get("lastStatus") if tasks else None
        if status == "STOPPED":
            return
        print(f"{label} status={status}; waiting", flush=True)
        time.sleep(10)


def _container_exit_result(
    cluster: str,
    task_arn: str,
    container_name: str,
    region: str,
) -> ProbeResult:
    response = _aws_json(
        ["ecs", "describe-tasks", "--cluster", cluster, "--tasks", task_arn],
        region,
    )
    task = response.get("tasks", [{}])[0]
    containers = task.get("containers", [])
    container = next(
        (
            item
            for item in containers
            if isinstance(item, dict) and item.get("name") == container_name
        ),
        {},
    )
    exit_code = container.get("exitCode")
    reason = container.get("reason") or task.get("stoppedReason") or ""
    return ProbeResult(
        exit_code == 0,
        f"ECS task {container_name}",
        f"exit_code={exit_code!r} reason={reason!r} task={task_arn}",
    )


def _worker_overrides() -> dict[str, Any]:
    max_batches = os.environ.get("BACKFILL_MAX_BATCHES", "1")
    return {
        "containerOverrides": [
            {
                "name": "worker",
                "environment": [
                    {"name": "BACKFILL_MAX_BATCHES", "value": max_batches},
                    {"name": "BACKFILL_SLEEP_MS", "value": "0"},
                ],
            }
        ]
    }


def _data_export_overrides() -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "containerOverrides": [
            {
                "name": "data-export-job",
                "environment": [
                    {
                        "name": "DATA_EXPORT_RUN_ID",
                        "value": f"observability-smoke-{now:%Y%m%dT%H%M%SZ}",
                    },
                    {"name": "DATA_EXPORT_DATE", "value": now.date().isoformat()},
                ],
            }
        ]
    }


def _liquibase_overrides() -> dict[str, Any]:
    return {
        "containerOverrides": [
            {
                "name": "liquibase",
                "command": [
                    "--search-path=/liquibase",
                    "--changelog-file=changelog/db.changelog-master.yaml",
                    "status",
                    "--verbose",
                ],
            }
        ]
    }


def _run_batch_target(
    *,
    target: str,
    stack_name: str,
    cluster: str,
    network: NetworkConfig,
    region: str,
) -> ProbeResult:
    overrides_by_target = {
        "worker": _worker_overrides,
        "data-export-job": _data_export_overrides,
        "liquibase": _liquibase_overrides,
    }
    task_arn = _run_task(
        cluster=cluster,
        task_definition=_task_definition(stack_name, target),
        container_name=target,
        network=network,
        region=region,
        overrides=overrides_by_target[target](),
    )
    _wait_task_stopped(cluster, task_arn, region, target)
    return _container_exit_result(cluster, task_arn, target, region)


def _restart_service(cluster: str, service: str, region: str) -> ProbeResult:
    _aws_json(
        [
            "ecs",
            "update-service",
            "--cluster",
            cluster,
            "--service",
            service,
            "--force-new-deployment",
        ],
        region,
    )
    _run(
        [
            "aws",
            "ecs",
            "wait",
            "services-stable",
            "--cluster",
            cluster,
            "--services",
            service,
            "--region",
            region,
        ]
    )
    return ProbeResult(True, f"ECS service {service}", "forced deployment stabilized")


def run() -> list[ProbeResult]:
    region = os.environ.get("AWS_REGION", "eu-central-1")
    stack_name = os.environ.get("STACK_NAME", "aws-sdlc-containers")
    cluster = os.environ.get("ECS_CLUSTER", stack_name)
    targets = _csv_env("OBSERVABILITY_CLOUD_JOB_TARGETS", DEFAULT_TARGETS)
    restart_daemons = _bool_env("OBSERVABILITY_RESTART_QUIET_DAEMONS", True)

    unknown = sorted(set(targets) - BATCH_TARGETS - DAEMON_TARGETS)
    if unknown:
        raise ValueError(
            f"Unknown observability cloud job targets: {', '.join(unknown)}"
        )

    network = _resolve_network(stack_name, region)
    results: list[ProbeResult] = []

    for target in targets:
        if target in BATCH_TARGETS:
            results.append(
                _run_batch_target(
                    target=target,
                    stack_name=stack_name,
                    cluster=cluster,
                    network=network,
                    region=region,
                )
            )
        elif restart_daemons:
            results.append(_restart_service(cluster, target, region))
        else:
            results.append(
                ProbeResult(
                    True,
                    f"ECS service {target}",
                    "skipped; OBSERVABILITY_RESTART_QUIET_DAEMONS is false",
                )
            )

    return results


def main() -> int:
    results = run()
    for result in results:
        prefix = "OK" if result.ok else "FAIL"
        stream = sys.stdout if result.ok else sys.stderr
        print(f"{prefix}: {result.label}: {result.detail}", file=stream)
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
