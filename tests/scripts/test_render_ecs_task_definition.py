from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import scripts.ci.render_ecs_task_definition as renderer  # noqa: E402


def test_render_primary_edge_task_definition_is_repo_sourced(monkeypatch) -> None:
    def fake_aws_json(args: list[str]) -> dict[str, Any]:
        if args[:2] == ["rds", "describe-db-instances"]:
            return {
                "DBInstances": [
                    {
                        "Endpoint": {"Address": "db.example.internal", "Port": 5432},
                        "MasterUserSecret": {
                            "SecretArn": "arn:aws:secretsmanager:eu-central-1:123:secret:rds"
                        },
                    }
                ]
            }
        raise AssertionError(f"unexpected aws call: {json.dumps(args)}")

    monkeypatch.setattr(renderer, "_aws_json", fake_aws_json)

    task_definition = renderer.render_task_definition(
        "aws-sdlc-containers",
        "api",
        "123.dkr.ecr.eu-central-1.amazonaws.com/aws-sdlc-containers/api:sha-new",
    )

    assert task_definition["family"] == "aws-sdlc-containers"
    assert (
        task_definition["cpu"]
        == renderer.AWS_RUNTIME_CLASS_DEFAULTS["edge-service"]["cpu"]
    )
    assert (
        task_definition["memory"]
        == renderer.AWS_RUNTIME_CLASS_DEFAULTS["edge-service"]["memory"]
    )
    assert (
        task_definition["taskRoleArn"]
        == "arn:aws:iam::123:role/aws-sdlc-containers-primary-edge-task"
    )

    containers = {
        container["name"]: container
        for container in task_definition["containerDefinitions"]
    }
    assert set(containers) == {"adot", "api", "pgbouncer"}
    assert containers["api"]["image"].endswith("/api:sha-new")
    assert containers["api"]["dependsOn"] == [
        {"containerName": "pgbouncer", "condition": "START"},
        {"containerName": "adot", "condition": "START"},
    ]
    assert containers["api"]["secrets"] == [
        {
            "name": "DB_PASSWORD",
            "valueFrom": "arn:aws:secretsmanager:eu-central-1:123:secret:rds:password::",
        },
        {
            "name": "PRIMARY_EDGE_AUTH_TOKEN",
            "valueFrom": "arn:aws:secretsmanager:eu-central-1:123:secret:aws-sdlc-containers/edge-token",
        },
    ]


def test_render_event_consumer_task_definition_includes_repo_owned_async_runtime(
    monkeypatch,
) -> None:
    def fake_aws_json(args: list[str]) -> dict[str, Any]:
        if args[:2] == ["rds", "describe-db-instances"]:
            return {
                "DBInstances": [
                    {
                        "Endpoint": {"Address": "db.example.internal", "Port": 5432},
                        "MasterUserSecret": {
                            "SecretArn": "arn:aws:secretsmanager:eu-central-1:123:secret:rds"
                        },
                    }
                ]
            }
        raise AssertionError(f"unexpected aws call: {json.dumps(args)}")

    monkeypatch.setattr(renderer, "_aws_json", fake_aws_json)

    task_definition = renderer.render_task_definition(
        "aws-sdlc-containers-event-consumer",
        "event-consumer",
        (
            "123.dkr.ecr.eu-central-1.amazonaws.com/"
            "aws-sdlc-containers/event-consumer:sha-new"
        ),
    )

    assert task_definition["family"] == "aws-sdlc-containers-event-consumer"
    assert task_definition["volumes"] == [{"name": "dapr-config"}]
    assert (
        task_definition["taskRoleArn"]
        == "arn:aws:iam::123:role/aws-sdlc-containers-event-consumer"
    )

    containers = {
        container["name"]: container
        for container in task_definition["containerDefinitions"]
    }
    assert set(containers) == {"dapr-config-loader", "daprd", "event-consumer"}
    assert containers["dapr-config-loader"]["entryPoint"] == ["/bin/sh", "-c"]
    assert (
        "s3://aws-sdlc-containers-runtime-config-123/config/dapr/event-consumer/"
        in containers["dapr-config-loader"]["command"][0]
    )
    assert containers["daprd"]["dependsOn"] == [
        {"containerName": "dapr-config-loader", "condition": "SUCCESS"}
    ]
    assert containers["event-consumer"]["image"].endswith("/event-consumer:sha-new")
    assert containers["event-consumer"]["environment"] == [
        {"name": "DB_HOST", "value": "db.example.internal"},
        {"name": "DB_PORT", "value": "5432"},
        {"name": "DB_USER", "value": "app"},
        {"name": "DB_NAME", "value": "aws_sdlc_containers"},
        {"name": "DAPR_HTTP_ENDPOINT", "value": "http://localhost:3500"},
        {"name": "DAPR_HTTP_PORT", "value": "3500"},
        {"name": "DAPR_PUBSUB_NAME", "value": "async-events-pubsub"},
        {
            "name": "DAPR_TOPIC",
            "value": "aws-sdlc-containers-async-events-v1.fifo",
        },
        {"name": "DAPR_SUBSCRIPTION_ROUTE", "value": "/internal/events/consume"},
    ]


def test_renderer_rejects_family_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(
        renderer,
        "_aws_json",
        lambda args: {
            "DBInstances": [
                {
                    "Endpoint": {"Address": "db.example.internal", "Port": 5432},
                    "MasterUserSecret": {
                        "SecretArn": "arn:aws:secretsmanager:eu-central-1:123:secret:rds"
                    },
                }
            ]
        },
    )

    try:
        renderer.render_task_definition(
            "wrong-family",
            "event-consumer",
            (
                "123.dkr.ecr.eu-central-1.amazonaws.com/"
                "aws-sdlc-containers/event-consumer:sha-new"
            ),
        )
    except RuntimeError as error:
        assert "does not match expected family" in str(error)
    else:
        raise AssertionError("expected family mismatch to raise")


def test_renderer_supports_runtime_override_env_for_restricted_local_runs(
    monkeypatch,
) -> None:
    monkeypatch.setenv("RUNTIME_DB_HOST", "db.override.internal")
    monkeypatch.setenv("RUNTIME_DB_PORT", "5432")
    monkeypatch.setenv(
        "RUNTIME_DB_SECRET_ARN",
        "arn:aws:secretsmanager:eu-central-1:123:secret:rds-override",
    )
    monkeypatch.setenv(
        "PRIMARY_EDGE_AUTH_SECRET_ARN",
        "arn:aws:secretsmanager:eu-central-1:123:secret:edge-override",
    )
    monkeypatch.setenv(
        "PRIMARY_EDGE_TASK_ROLE_ARN",
        "arn:aws:iam::123:role/primary-edge-task-override",
    )

    def fail_if_called(args: list[str]) -> dict[str, Any]:
        raise AssertionError(f"unexpected aws call: {json.dumps(args)}")

    monkeypatch.setattr(renderer, "_aws_json", fail_if_called)

    task_definition = renderer.render_task_definition(
        "aws-sdlc-containers",
        "api",
        "123.dkr.ecr.eu-central-1.amazonaws.com/aws-sdlc-containers/api:sha-new",
    )

    containers = {
        container["name"]: container
        for container in task_definition["containerDefinitions"]
    }
    assert (
        task_definition["taskRoleArn"]
        == "arn:aws:iam::123:role/primary-edge-task-override"
    )
    assert any(
        env == {"name": "DB_HOST", "value": "db.override.internal"}
        for env in containers["pgbouncer"]["environment"]
    )
    assert any(
        env == {"name": "DB_HOST", "value": "127.0.0.1"}
        for env in containers["api"]["environment"]
    )
    assert containers["api"]["secrets"] == [
        {
            "name": "DB_PASSWORD",
            "valueFrom": "arn:aws:secretsmanager:eu-central-1:123:secret:rds-override:password::",
        },
        {
            "name": "PRIMARY_EDGE_AUTH_TOKEN",
            "valueFrom": "arn:aws:secretsmanager:eu-central-1:123:secret:edge-override",
        },
    ]


def test_backfill_renderer_uses_repository_scoped_support_job_role(
    monkeypatch,
) -> None:
    def fake_aws_json(args: list[str]) -> dict[str, Any]:
        if args[:2] == ["rds", "describe-db-instances"]:
            return {
                "DBInstances": [
                    {
                        "Endpoint": {"Address": "db.example.internal", "Port": 5432},
                        "MasterUserSecret": {
                            "SecretArn": "arn:aws:secretsmanager:eu-central-1:123:secret:rds"
                        },
                    }
                ]
            }
        raise AssertionError(f"unexpected aws call: {json.dumps(args)}")

    monkeypatch.setattr(renderer, "_aws_json", fake_aws_json)

    task_definition = renderer.render_task_definition(
        "aws-sdlc-containers-backfill-worker",
        "backfill-worker",
        (
            "123.dkr.ecr.eu-central-1.amazonaws.com/"
            "aws-sdlc-containers/backfill-worker:sha-new"
        ),
    )

    assert (
        task_definition["taskRoleArn"]
        == "arn:aws:iam::123:role/aws-sdlc-containers-backfill-worker"
    )
    container = task_definition["containerDefinitions"][0]
    env_names = {entry["name"] for entry in container["environment"]}
    assert "BACKFILL_BATCH_SIZE" not in env_names
    assert "BACKFILL_SLEEP_MS" not in env_names


def test_renderer_class_defaults_align_with_terraform_bootstrap_defaults() -> None:
    workload_inventory = (ROOT / "infra/app/workload_inventory.tf").read_text(
        encoding="utf-8"
    )

    parsed_defaults: dict[str, dict[str, str]] = {}
    for class_name in renderer.AWS_RUNTIME_CLASS_DEFAULTS:
        block_match = re.search(
            rf"{re.escape(class_name)} = \{{(?P<body>.*?)^\s+\}}",
            workload_inventory,
            re.MULTILINE | re.DOTALL,
        )
        assert block_match is not None
        parsed_defaults[class_name] = dict(
            re.findall(r"(cpu|memory)\s*=\s*(\d+)", block_match.group("body"))
        )

    assert parsed_defaults == renderer.AWS_RUNTIME_CLASS_DEFAULTS
