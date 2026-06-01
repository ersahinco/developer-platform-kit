from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import scripts.ci.resolve_ecs_task_context as resolver


ROOT = Path(__file__).resolve().parents[2]


def test_resolve_ecs_task_context_outputs_network_logs_and_task_definition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_aws_json(args: list[str], *, region: str) -> dict[str, Any]:
        calls.append(args)
        assert region == "eu-central-1"
        if args[:2] == ["ec2", "describe-subnets"]:
            return {"Subnets": [{"SubnetId": "subnet-123"}]}
        if args[:2] == ["ec2", "describe-security-groups"]:
            return {"SecurityGroups": [{"GroupId": "sg-123"}]}
        if args[:2] == ["logs", "describe-log-groups"]:
            return {
                "logGroups": [
                    {
                        "logGroupName": (
                            "/ecs/aws-sdlc-containers/operational-snapshot-job"
                        )
                    }
                ]
            }
        if args[:2] == ["ecs", "describe-task-definition"]:
            return {
                "taskDefinition": {
                    "taskDefinitionArn": "arn:task-definition:2",
                    "containerDefinitions": [
                        {
                            "name": "operational-snapshot-job",
                            "image": (
                                "123.dkr.ecr.eu-central-1.amazonaws.com/"
                                "aws-sdlc-containers/operational-snapshot-job:sha-123"
                            ),
                        }
                    ],
                }
            }
        raise AssertionError(f"unexpected AWS args: {args}")

    monkeypatch.setattr(resolver, "_aws_json", fake_aws_json)

    context = resolver.resolve_context(
        stack_name="aws-sdlc-containers",
        repository="operational-snapshot-job",
        family=None,
        region="eu-central-1",
        resolve_task_definition=True,
        verify_log_group=True,
    )

    assert context == {
        "family": "aws-sdlc-containers-operational-snapshot-job",
        "repository": "operational-snapshot-job",
        "log_group": "/ecs/aws-sdlc-containers/operational-snapshot-job",
        "subnet_id": "subnet-123",
        "sg_id": "sg-123",
        "task_definition": "arn:task-definition:2",
        "image": (
            "123.dkr.ecr.eu-central-1.amazonaws.com/"
            "aws-sdlc-containers/operational-snapshot-job:sha-123"
        ),
        "image_tag": "sha-123",
    }
    assert [
        "logs",
        "describe-log-groups",
        "--log-group-name-prefix",
        context["log_group"],
    ] in calls


def test_resolve_ecs_task_context_rejects_missing_log_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_aws_json(args: list[str], *, region: str) -> dict[str, Any]:
        if args[:2] == ["ec2", "describe-subnets"]:
            return {"Subnets": [{"SubnetId": "subnet-123"}]}
        if args[:2] == ["ec2", "describe-security-groups"]:
            return {"SecurityGroups": [{"GroupId": "sg-123"}]}
        if args[:2] == ["logs", "describe-log-groups"]:
            return {"logGroups": []}
        raise AssertionError(f"unexpected AWS args: {args}")

    monkeypatch.setattr(resolver, "_aws_json", fake_aws_json)

    with pytest.raises(RuntimeError, match="log group .* was not found"):
        resolver.resolve_context(
            stack_name="aws-sdlc-containers",
            repository="backfill-worker",
            family=None,
            region="eu-central-1",
            resolve_task_definition=False,
            verify_log_group=True,
        )


def test_resolve_ecs_task_context_cli_outputs_github_lines(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        resolver,
        "resolve_context",
        lambda **_kwargs: {
            "family": "aws-sdlc-containers-backfill-worker",
            "repository": "backfill-worker",
            "subnet_id": "subnet-123",
            "sg_id": "sg-123",
            "log_group": "/ecs/aws-sdlc-containers/backfill-worker",
        },
    )

    assert (
        resolver.main(
            [
                "--stack-name",
                "aws-sdlc-containers",
                "--repository",
                "backfill-worker",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "subnet_id=subnet-123" in output
    assert "sg_id=sg-123" in output


def test_resolve_ecs_task_context_cli_outputs_json() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/ci/resolve_ecs_task_context.py",
            "--help",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert "Resolve conventional ECS run-task context" in completed.stdout
