#!/usr/bin/env python3
"""Register and deploy an ECS app task definition with a new app image."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

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


def _image_from_env() -> str:
    explicit_image = os.environ.get("APP_IMAGE")
    if explicit_image:
        return explicit_image

    tag = os.environ.get("APP_IMAGE_TAG")
    if not tag:
        raise RuntimeError("Set APP_IMAGE_TAG or APP_IMAGE")

    region = os.environ.get("AWS_REGION", "eu-central-1")
    account_id = os.environ.get("ACCOUNT_ID", "691627364817")
    stack_name = os.environ.get("STACK_NAME", "aws-sdlc-containers")
    return f"{account_id}.dkr.ecr.{region}.amazonaws.com/{stack_name}/app:{tag}"


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


def _register_app_revision(region: str, app_image: str) -> str:
    description = _describe_task_definition("aws-sdlc-containers", region)
    task_definition = description["taskDefinition"]
    payload = {
        key: task_definition[key]
        for key in REGISTER_FIELDS
        if key in task_definition and task_definition[key] not in (None, [], {})
    }

    for container in payload["containerDefinitions"]:
        if container.get("name") == "app":
            container["image"] = app_image
            break
    else:
        raise RuntimeError("aws-sdlc-containers task definition has no app container")

    tags = description.get("tags", [])
    if tags:
        payload["tags"] = tags

    path = ROOT / ".tmp" / "aws-sdlc-containers-app-roll.json"
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
    print(f"Registered app task definition: {task_definition_arn}")
    return task_definition_arn


def main() -> int:
    region = os.environ.get("AWS_REGION", "eu-central-1")
    cluster = os.environ.get("ECS_CLUSTER", "aws-sdlc-containers")
    service = os.environ.get("ECS_SERVICE", "app")
    app_image = _image_from_env()
    task_definition_arn = _register_app_revision(region, app_image)

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
    print(f"Updated {service} to {task_definition_arn}")

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
    print("App rollout complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
