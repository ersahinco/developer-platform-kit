#!/usr/bin/env python3
"""Register ECS task definition revisions with a new FireLens image."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

SERVICE_FAMILIES = {
    "app": "aws-sdlc-containers",
    "order-event-consumer": "aws-sdlc-containers-order-event-consumer",
    "grafana": "aws-sdlc-containers-grafana",
    "loki": "aws-sdlc-containers-loki",
    "prometheus": "aws-sdlc-containers-prometheus",
    "tempo": "aws-sdlc-containers-tempo",
}

TASK_ONLY_FAMILIES = [
    "aws-sdlc-containers-worker",
    "aws-sdlc-containers-data-export-job",
    "aws-sdlc-containers-liquibase",
]

REGISTER_FIELDS = [
    "family",
    "taskRoleArn",
    "executionRoleArn",
    "networkMode",
    "containerDefinitions",
    "volumes",
    "placementConstraints",
    "requiresCompatibilities",
    "cpu",
    "memory",
    "pidMode",
    "ipcMode",
    "proxyConfiguration",
    "inferenceAccelerators",
    "ephemeralStorage",
    "runtimePlatform",
]


def _run(command: list[str]) -> str:
    result = subprocess.run(
        command,
        check=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.stdout


def _describe_task_definition(family: str, region: str) -> dict[str, Any]:
    return json.loads(
        _run(
            [
                "aws",
                "ecs",
                "describe-task-definition",
                "--task-definition",
                family,
                "--include",
                "TAGS",
                "--region",
                region,
                "--output",
                "json",
            ]
        )
    )


def _register_payload(
    description: dict[str, Any],
    firelens_image: str,
) -> dict[str, Any]:
    task_definition = description["taskDefinition"]
    payload = {
        key: task_definition[key]
        for key in REGISTER_FIELDS
        if key in task_definition and task_definition[key] not in (None, [], {})
    }

    updated = False
    for container in payload["containerDefinitions"]:
        if container.get("name") == "log-router":
            container["image"] = firelens_image
            updated = True
            break
    if not updated:
        raise RuntimeError(f"{task_definition['family']} has no log-router container")

    tags = description.get("tags", [])
    if tags:
        payload["tags"] = tags
    return payload


def _register_revision(
    family: str,
    firelens_image: str,
    region: str,
) -> str:
    description = _describe_task_definition(family, region)
    payload = _register_payload(description, firelens_image)
    path = ROOT / ".tmp" / f"{family}-firelens-roll.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    task_definition_arn = _run(
        [
            "aws",
            "ecs",
            "register-task-definition",
            "--cli-input-json",
            f"file://{path}",
            "--region",
            region,
            "--query",
            "taskDefinition.taskDefinitionArn",
            "--output",
            "text",
        ]
    ).strip()
    print(f"Registered {family}: {task_definition_arn}")
    return task_definition_arn


def _update_service(
    cluster: str,
    service: str,
    task_definition_arn: str,
    region: str,
) -> None:
    _run(
        [
            "aws",
            "ecs",
            "update-service",
            "--cluster",
            cluster,
            "--service",
            service,
            "--task-definition",
            task_definition_arn,
            "--region",
            region,
            "--output",
            "json",
        ]
    )
    print(f"Updated service {service}")


def _wait_service(cluster: str, service: str, region: str) -> None:
    print(f"Waiting for {service} to stabilize")
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


def _firelens_image() -> str:
    explicit_image = os.environ.get("FIRELENS_IMAGE")
    if explicit_image:
        return explicit_image

    tag = os.environ.get("FIRELENS_IMAGE_TAG")
    if not tag:
        raise RuntimeError("Set FIRELENS_IMAGE_TAG or FIRELENS_IMAGE")

    region = os.environ.get("AWS_REGION", "eu-central-1")
    account_id = os.environ.get("ACCOUNT_ID", "691627364817")
    stack_name = os.environ.get("STACK_NAME", "aws-sdlc-containers")
    return f"{account_id}.dkr.ecr.{region}.amazonaws.com/{stack_name}/firelens:{tag}"


def main() -> int:
    region = os.environ.get("AWS_REGION", "eu-central-1")
    cluster = os.environ.get("ECS_CLUSTER", "aws-sdlc-containers")
    firelens_image = _firelens_image()

    service_updates: list[tuple[str, str]] = []
    for service, family in SERVICE_FAMILIES.items():
        task_definition_arn = _register_revision(family, firelens_image, region)
        service_updates.append((service, task_definition_arn))

    for family in TASK_ONLY_FAMILIES:
        _register_revision(family, firelens_image, region)

    for service, task_definition_arn in service_updates:
        _update_service(cluster, service, task_definition_arn, region)

    for service, _task_definition_arn in service_updates:
        _wait_service(cluster, service, region)

    print("FireLens image rollout complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
