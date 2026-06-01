#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def _aws_json(args: list[str], *, region: str) -> dict[str, Any]:
    completed = subprocess.run(
        ["aws", *args, "--region", region, "--output", "json"],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    data = json.loads(completed.stdout or "{}")
    if not isinstance(data, dict):
        raise RuntimeError(f"expected object from AWS CLI for {' '.join(args)}")
    return data


def _first_subnet_id(stack_name: str, *, region: str) -> str:
    data = _aws_json(
        [
            "ec2",
            "describe-subnets",
            "--filters",
            f"Name=tag:Name,Values={stack_name}-private-*",
        ],
        region=region,
    )
    subnets = data.get("Subnets", [])
    if not isinstance(subnets, list) or not subnets:
        raise RuntimeError(f"failed to resolve private subnet for stack {stack_name}")
    subnet_id = subnets[0].get("SubnetId")
    if not isinstance(subnet_id, str) or not subnet_id:
        raise RuntimeError(f"failed to resolve private subnet for stack {stack_name}")
    return subnet_id


def _primary_edge_security_group_id(stack_name: str, *, region: str) -> str:
    data = _aws_json(
        [
            "ec2",
            "describe-security-groups",
            "--filters",
            f"Name=group-name,Values={stack_name}-primary-edge-*",
        ],
        region=region,
    )
    groups = data.get("SecurityGroups", [])
    if not isinstance(groups, list) or not groups:
        raise RuntimeError(
            f"failed to resolve primary edge security group for stack {stack_name}"
        )
    group_id = groups[0].get("GroupId")
    if not isinstance(group_id, str) or not group_id:
        raise RuntimeError(
            f"failed to resolve primary edge security group for stack {stack_name}"
        )
    return group_id


def _task_definition_context(
    family: str,
    repository: str,
    *,
    region: str,
) -> dict[str, str]:
    data = _aws_json(
        ["ecs", "describe-task-definition", "--task-definition", family],
        region=region,
    )
    task_definition = data.get("taskDefinition", {})
    if not isinstance(task_definition, dict):
        raise RuntimeError(f"failed to resolve task definition for {family}")
    task_definition_arn = task_definition.get("taskDefinitionArn")
    if not isinstance(task_definition_arn, str) or not task_definition_arn:
        raise RuntimeError(f"failed to resolve task definition for {family}")

    containers = task_definition.get("containerDefinitions", [])
    image = None
    if isinstance(containers, list):
        for container in containers:
            if not isinstance(container, dict):
                continue
            if container.get("name") == repository:
                candidate = container.get("image")
                if isinstance(candidate, str) and candidate:
                    image = candidate
                break
    if image is None:
        raise RuntimeError(f"failed to resolve image for container {repository}")

    return {
        "task_definition": task_definition_arn,
        "image": image,
        "image_tag": image.rsplit(":", 1)[-1],
    }


def _require_log_group(log_group: str, *, region: str) -> None:
    data = _aws_json(
        ["logs", "describe-log-groups", "--log-group-name-prefix", log_group],
        region=region,
    )
    groups = data.get("logGroups", [])
    if not isinstance(groups, list):
        raise RuntimeError(f"failed to verify log group {log_group}")
    if not any(
        isinstance(group, dict) and group.get("logGroupName") == log_group
        for group in groups
    ):
        raise RuntimeError(f"log group {log_group} was not found")


def resolve_context(
    *,
    stack_name: str,
    repository: str,
    family: str | None,
    region: str,
    resolve_task_definition: bool,
    verify_log_group: bool,
) -> dict[str, str]:
    resolved_family = family or f"{stack_name}-{repository}"
    log_group = f"/ecs/{stack_name}/{repository}"
    context = {
        "family": resolved_family,
        "repository": repository,
        "log_group": log_group,
        "subnet_id": _first_subnet_id(stack_name, region=region),
        "sg_id": _primary_edge_security_group_id(stack_name, region=region),
    }
    if verify_log_group:
        _require_log_group(log_group, region=region)
    if resolve_task_definition:
        context.update(
            _task_definition_context(resolved_family, repository, region=region)
        )
    return context


def _github_output(context: dict[str, str]) -> str:
    return "".join(f"{key}={value}\n" for key, value in sorted(context.items()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Resolve conventional ECS run-task context for GitHub workflows."
    )
    parser.add_argument("--stack-name", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--family")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "eu-central-1"))
    parser.add_argument("--resolve-task-definition", action="store_true")
    parser.add_argument("--verify-log-group", action="store_true")
    parser.add_argument("--format", choices=["github", "json"], default="github")
    args = parser.parse_args(argv)

    try:
        context = resolve_context(
            stack_name=args.stack_name,
            repository=args.repository,
            family=args.family,
            region=args.region,
            resolve_task_definition=args.resolve_task_definition,
            verify_log_group=args.verify_log_group,
        )
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(context, sort_keys=True))
    else:
        print(_github_output(context), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
