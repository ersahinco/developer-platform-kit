#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.platform.workload_metadata import (  # noqa: E402
    workload_operational_class,
    workload_repository,
    workloads,
)

DEFAULT_DB_NAME = "aws_sdlc_containers"
DEFAULT_DB_USER = "app"
AWS_RUNTIME_CLASS_DEFAULTS = {
    "edge-service": {
        "cpu": "512",
        "memory": "1024",
    },
    "internal-service": {
        "cpu": "512",
        "memory": "1024",
    },
    "operator-job": {
        "cpu": "256",
        "memory": "512",
    },
    "scheduled-job": {
        "cpu": "256",
        "memory": "512",
    },
}
DEFAULT_LIQUIBASE_CPU = "512"
DEFAULT_LIQUIBASE_MEMORY = "1024"
DEFAULT_PGBOUNCER_POOL_SIZE = "20"
DEFAULT_PGBOUNCER_TAG = "v1.25.1-p0"
DEFAULT_DAPR_IMAGE = "daprio/daprd:1.17.0"
DEFAULT_RUNTIME_CONFIG_LOADER_IMAGE = "public.ecr.aws/aws-cli/aws-cli:2.32.3"
DEFAULT_ADOT_COLLECTOR_IMAGE = (
    "public.ecr.aws/aws-observability/aws-otel-collector:v0.47.0"
)


def _workloads_by_repository() -> dict[str, dict[str, Any]]:
    return {
        workload_repository(workload): workload
        for workload in workloads()
        if workload_repository(workload)
    }


def _aws_json(args: list[str]) -> dict[str, Any]:
    region = os.getenv("AWS_REGION", "eu-central-1")
    try:
        completed = subprocess.run(
            ["aws", *args, "--region", region, "--output", "json"],
            check=True,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
    except subprocess.CalledProcessError as error:
        stderr = error.stderr.strip() or error.stdout.strip() or str(error)
        command = " ".join(error.cmd)
        if "Could not connect to the endpoint URL" in stderr:
            stderr = (
                f"{stderr}\n"
                "If you are running in a restricted local environment, provide "
                "RUNTIME_DB_HOST, RUNTIME_DB_PORT, RUNTIME_DB_SECRET_ARN, and "
                "PRIMARY_EDGE_AUTH_SECRET_ARN to "
                "bypass live runtime lookups."
            )
        raise RuntimeError(f"AWS CLI call failed: {command}\n{stderr}") from error
    data = json.loads(completed.stdout)
    assert isinstance(data, dict)
    return data


def _log_configuration(group: str, region: str, stream_prefix: str) -> dict[str, Any]:
    return {
        "logDriver": "awslogs",
        "options": {
            "awslogs-group": group,
            "awslogs-region": region,
            "awslogs-stream-prefix": stream_prefix,
        },
    }


def _health_check(port: int, *, interval: int, start_period: int) -> dict[str, Any]:
    return {
        "command": [
            "CMD-SHELL",
            (
                "python -c "
                f"\"import urllib.request; urllib.request.urlopen('http://localhost:{port}/health')\""
            ),
        ],
        "interval": interval,
        "timeout": 3,
        "retries": 3,
        "startPeriod": start_period,
    }


def _container_defaults() -> dict[str, Any]:
    return {
        "cpu": 0,
        "environment": [],
        "mountPoints": [],
        "portMappings": [],
        "systemControls": [],
        "volumesFrom": [],
    }


def _merge_container(overrides: dict[str, Any]) -> dict[str, Any]:
    merged = {**_container_defaults(), **overrides}
    return merged


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _default_adot_config(repository: str, service_port: int) -> str:
    return "\n".join(
        [
            "receivers:",
            "  otlp:",
            "    protocols:",
            "      grpc:",
            "        endpoint: 0.0.0.0:4317",
            "      http:",
            "        endpoint: 0.0.0.0:4318",
            "  prometheus:",
            "    config:",
            "      scrape_configs:",
            f"        - job_name: {repository}",
            "          metrics_path: /metrics",
            "          static_configs:",
            f'            - targets: ["127.0.0.1:{service_port}"]',
            "exporters:",
            "  debug:",
            "    verbosity: basic",
            "service:",
            "  pipelines:",
            "    metrics:",
            "      receivers: [prometheus]",
            "      exporters: [debug]",
            "    traces:",
            "      receivers: [otlp]",
            "      exporters: [debug]",
        ]
    )


def _deterministic_role_arn(account_id: str, role_name: str) -> str:
    return f"arn:aws:iam::{account_id}:role/{role_name}"


def _deterministic_secret_arn(
    *,
    account_id: str,
    region: str,
    secret_name: str,
) -> str:
    return f"arn:aws:secretsmanager:{region}:{account_id}:secret:{secret_name}"


def _primary_edge_task_role_name(stack_name: str) -> str:
    return f"{stack_name}-primary-edge-task"


def _repository_from_image(image: str) -> tuple[str, str, str]:
    registry, remainder = image.split("/", 1)
    stack_name, repository_with_tag = remainder.split("/", 1)
    repository = repository_with_tag.rsplit(":", 1)[0]
    return registry, stack_name, repository


def _account_id_from_registry(registry: str) -> str:
    return registry.split(".", 1)[0]


def _resolve_database_runtime(stack_name: str) -> dict[str, Any]:
    overridden_address = os.getenv("RUNTIME_DB_HOST")
    overridden_port = os.getenv("RUNTIME_DB_PORT")
    overridden_secret_arn = os.getenv("RUNTIME_DB_SECRET_ARN")
    if overridden_address and overridden_port and overridden_secret_arn:
        return {
            "address": overridden_address,
            "port": int(overridden_port),
            "secret_arn": overridden_secret_arn,
        }

    document = _aws_json(
        [
            "rds",
            "describe-db-instances",
            "--db-instance-identifier",
            stack_name,
        ]
    )
    instance = document["DBInstances"][0]
    return {
        "address": instance["Endpoint"]["Address"],
        "port": int(instance["Endpoint"]["Port"]),
        "secret_arn": instance["MasterUserSecret"]["SecretArn"],
    }


def _resolve_primary_edge_auth_secret_arn(
    secret_name: str,
    *,
    account_id: str,
    region: str,
) -> str:
    overridden_arn = os.getenv("PRIMARY_EDGE_AUTH_SECRET_ARN")
    if overridden_arn:
        return overridden_arn
    return _deterministic_secret_arn(
        account_id=account_id,
        region=region,
        secret_name=secret_name,
    )


def _resolve_primary_edge_task_role_arn(
    stack_name: str,
    *,
    account_id: str,
) -> str:
    overridden_arn = os.getenv("PRIMARY_EDGE_TASK_ROLE_ARN")
    if overridden_arn:
        return overridden_arn
    return _deterministic_role_arn(account_id, _primary_edge_task_role_name(stack_name))


def _declared_environment(
    workload: dict[str, Any],
    runtime_values: dict[str, str],
) -> list[dict[str, str]]:
    config = workload.get("config", {})
    declared = config.get("env", []) if isinstance(config, dict) else []
    return [
        {"name": env_name, "value": runtime_values[env_name]}
        for env_name in declared
        if isinstance(env_name, str) and env_name in runtime_values
    ]


def _declared_env_names(workload: dict[str, Any]) -> set[str]:
    config = workload.get("config", {})
    declared = config.get("env", []) if isinstance(config, dict) else []
    return {env_name for env_name in declared if isinstance(env_name, str) and env_name}


def _declared_secrets(
    workload: dict[str, Any],
    secret_values: dict[str, str],
) -> list[dict[str, str]]:
    config = workload.get("config", {})
    declared = config.get("secrets", []) if isinstance(config, dict) else []
    return [
        {"name": secret_name, "valueFrom": secret_values[secret_name]}
        for secret_name in declared
        if isinstance(secret_name, str) and secret_name in secret_values
    ]


def _runtime_values_for_workload(
    workload: dict[str, Any],
    *,
    stack_name: str,
    region: str,
    db_address: str,
    db_port: int,
    data_hub_bucket_name: str,
    enable_adot_sidecar: bool,
) -> dict[str, str]:
    values: dict[str, str] = {}
    declared_env_names = _declared_env_names(workload)

    database = workload.get("database")
    if isinstance(database, dict):
        values["DB_USER"] = DEFAULT_DB_USER
        values["DB_NAME"] = DEFAULT_DB_NAME
        if database.get("pooling") == "transaction_pool":
            values["DB_HOST"] = "127.0.0.1"
            values["DB_PORT"] = "5432"
        else:
            values["DB_HOST"] = db_address
            values["DB_PORT"] = str(db_port)

    repository = workload_repository(workload)
    if workload.get("traces", {}).get("supported") is True:
        trace_endpoint = (
            "http://127.0.0.1:4318/v1/traces" if enable_adot_sidecar else ""
        )
        if trace_endpoint:
            values.update(
                {
                    "OTEL_TRACES_ENABLED": "true",
                    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": trace_endpoint,
                    "OTEL_SERVICE_NAME": f"{stack_name}-{repository}",
                    "OTEL_DEPLOYMENT_ENVIRONMENT": "aws",
                }
            )

    if isinstance(workload.get("dapr"), dict):
        values["DAPR_HTTP_ENDPOINT"] = "http://localhost:3500"
        values["DAPR_HTTP_PORT"] = "3500"

    if workload_operational_class(workload) == "edge-service":
        values.update(
            {
                "ROLLOUT_DRILL_FAULT_MODE": "off",
                "ROLLOUT_DRILL_FAULT_PATHS": "/ready",
                "ROLLOUT_DRILL_FAULT_STATUS_CODE": "503",
                "ROLLOUT_DRILL_FAULT_DELAY_SECONDS": "3",
            }
        )

    env_defaults = {
        "DATA_EXPORT_S3_BUCKET": data_hub_bucket_name,
    }
    dapr = workload.get("dapr")
    if isinstance(dapr, dict):
        env_defaults.update(
            {
                "DAPR_PUBSUB_NAME": str(dapr["pubsub_name"]),
                "DAPR_TOPIC": f"{stack_name}-{dapr['topic']}",
                "DAPR_SUBSCRIPTION_ROUTE": str(dapr["subscription_route"]),
            }
        )
    values.update(
        {
            env_name: value
            for env_name, value in env_defaults.items()
            if env_name in declared_env_names
        }
    )

    return values


def _runtime_secrets_for_workload(
    workload: dict[str, Any],
    *,
    db_secret_arn: str,
    primary_edge_auth_secret_arn: str | None,
) -> dict[str, str]:
    values = {
        "DB_PASSWORD": f"{db_secret_arn}:password::",
    }
    if primary_edge_auth_secret_arn is not None:
        values["PRIMARY_EDGE_AUTH_TOKEN"] = primary_edge_auth_secret_arn
    return values


def _expected_task_family(
    stack_name: str, workload: dict[str, Any] | None, container_name: str
) -> str:
    if workload is None:
        if container_name != "liquibase":
            raise RuntimeError(f"unsupported platform container {container_name}")
        return f"{stack_name}-liquibase"

    operational_class = workload_operational_class(workload)
    if operational_class == "edge-service":
        return stack_name
    return f"{stack_name}-{container_name}"


def _runtime_shape_for_workload(workload: dict[str, Any]) -> dict[str, str]:
    operational_class = workload_operational_class(workload)
    try:
        return AWS_RUNTIME_CLASS_DEFAULTS[operational_class]
    except KeyError as error:
        raise RuntimeError(
            f"unsupported workload operational class {operational_class!r}"
        ) from error


def _render_primary_edge(
    workload: dict[str, Any],
    *,
    stack_name: str,
    region: str,
    account_id: str,
    image: str,
    db_address: str,
    db_port: int,
    db_secret_arn: str,
    primary_edge_auth_secret_arn: str,
    primary_edge_task_role_arn: str,
) -> dict[str, Any]:
    repository = workload_repository(workload)
    service_port = int(workload["service"]["port"])
    runtime_shape = _runtime_shape_for_workload(workload)
    enable_adot_sidecar = _parse_bool(os.getenv("ENABLE_ADOT_SIDECAR"), default=True)
    declared_env = _declared_environment(
        workload,
        _runtime_values_for_workload(
            workload,
            stack_name=stack_name,
            region=region,
            db_address=db_address,
            db_port=db_port,
            data_hub_bucket_name=f"{stack_name}-data-hub-{account_id}",
            enable_adot_sidecar=enable_adot_sidecar,
        ),
    )
    declared_secrets = _declared_secrets(
        workload,
        _runtime_secrets_for_workload(
            workload,
            db_secret_arn=db_secret_arn,
            primary_edge_auth_secret_arn=primary_edge_auth_secret_arn,
        ),
    )

    container_definitions: list[dict[str, Any]] = []
    if enable_adot_sidecar:
        container_definitions.append(
            _merge_container(
                {
                    "name": "adot",
                    "image": os.getenv(
                        "ADOT_COLLECTOR_IMAGE", DEFAULT_ADOT_COLLECTOR_IMAGE
                    ),
                    "essential": True,
                    "command": ["--config=env:ADOT_COLLECTOR_CONFIG"],
                    "environment": [
                        {
                            "name": "ADOT_COLLECTOR_CONFIG",
                            "value": os.getenv(
                                "ADOT_COLLECTOR_CONFIG",
                                _default_adot_config(repository, service_port),
                            ),
                        },
                        {"name": "AWS_REGION", "value": region},
                    ],
                    "portMappings": [
                        {
                            "containerPort": 4317,
                            "hostPort": 4317,
                            "protocol": "tcp",
                        },
                        {
                            "containerPort": 4318,
                            "hostPort": 4318,
                            "protocol": "tcp",
                        },
                    ],
                    "readonlyRootFilesystem": False,
                }
            )
        )

    container_definitions.append(
        _merge_container(
            {
                "name": repository,
                "image": image,
                "essential": True,
                "portMappings": [
                    {
                        "containerPort": service_port,
                        "hostPort": service_port,
                        "protocol": "tcp",
                    }
                ],
                "environment": declared_env,
                "secrets": declared_secrets,
                "dependsOn": [
                    {"containerName": "pgbouncer", "condition": "START"},
                    *(
                        [{"containerName": "adot", "condition": "START"}]
                        if enable_adot_sidecar
                        else []
                    ),
                ],
                "healthCheck": _health_check(service_port, interval=5, start_period=15),
                "readonlyRootFilesystem": False,
            }
        )
    )

    container_definitions.append(
        _merge_container(
            {
                "name": "pgbouncer",
                "image": (
                    f"{account_id}.dkr.ecr.{region}.amazonaws.com/"
                    f"{stack_name}/pgbouncer:{os.getenv('PGBOUNCER_TAG', DEFAULT_PGBOUNCER_TAG)}"
                ),
                "essential": True,
                "environment": [
                    {"name": "DB_HOST", "value": db_address},
                    {"name": "DB_PORT", "value": str(db_port)},
                    {"name": "DB_NAME", "value": DEFAULT_DB_NAME},
                    {"name": "POOL_MODE", "value": "transaction"},
                    {
                        "name": "DEFAULT_POOL_SIZE",
                        "value": os.getenv(
                            "PGBOUNCER_POOL_SIZE", DEFAULT_PGBOUNCER_POOL_SIZE
                        ),
                    },
                    {"name": "MAX_CLIENT_CONN", "value": "200"},
                    {"name": "AUTH_TYPE", "value": "scram-sha-256"},
                    {"name": "STATS_PERIOD", "value": "3600"},
                ],
                "secrets": [
                    {"name": "DB_USER", "valueFrom": f"{db_secret_arn}:username::"},
                    {"name": "DB_PASSWORD", "valueFrom": f"{db_secret_arn}:password::"},
                ],
                "readonlyRootFilesystem": False,
            }
        )
    )

    return {
        "family": stack_name,
        "requiresCompatibilities": ["FARGATE"],
        "networkMode": "awsvpc",
        "cpu": runtime_shape["cpu"],
        "memory": runtime_shape["memory"],
        "executionRoleArn": _deterministic_role_arn(
            account_id, f"{stack_name}-task-exec"
        ),
        "taskRoleArn": primary_edge_task_role_arn,
        "containerDefinitions": container_definitions,
    }


def _render_support_job(
    workload: dict[str, Any],
    *,
    stack_name: str,
    region: str,
    account_id: str,
    image: str,
    db_address: str,
    db_port: int,
    db_secret_arn: str,
    task_role_arn: str,
) -> dict[str, Any]:
    repository = workload_repository(workload)
    runtime_shape = _runtime_shape_for_workload(workload)
    runtime_values = _runtime_values_for_workload(
        workload,
        stack_name=stack_name,
        region=region,
        db_address=db_address,
        db_port=db_port,
        data_hub_bucket_name=f"{stack_name}-data-hub-{account_id}",
        enable_adot_sidecar=False,
    )
    container = _merge_container(
        {
            "name": repository,
            "image": image,
            "essential": True,
            "environment": _declared_environment(workload, runtime_values),
            "secrets": _declared_secrets(
                workload,
                _runtime_secrets_for_workload(
                    workload,
                    db_secret_arn=db_secret_arn,
                    primary_edge_auth_secret_arn=None,
                ),
            ),
            "logConfiguration": _log_configuration(
                f"/ecs/{stack_name}/{repository}",
                region,
                repository,
            ),
        }
    )

    return {
        "family": f"{stack_name}-{repository}",
        "requiresCompatibilities": ["FARGATE"],
        "networkMode": "awsvpc",
        "cpu": runtime_shape["cpu"],
        "memory": runtime_shape["memory"],
        "executionRoleArn": _deterministic_role_arn(
            account_id, f"{stack_name}-task-exec"
        ),
        "taskRoleArn": task_role_arn,
        "containerDefinitions": [container],
    }


def _render_internal_async_service(
    workload: dict[str, Any],
    *,
    stack_name: str,
    region: str,
    account_id: str,
    image: str,
    db_address: str,
    db_port: int,
    db_secret_arn: str,
) -> dict[str, Any]:
    repository = workload_repository(workload)
    service_port = int(workload["service"]["port"])
    runtime_shape = _runtime_shape_for_workload(workload)
    dapr = workload["dapr"]
    runtime_config_bucket = f"{stack_name}-runtime-config-{account_id}"
    config_prefix = f"config/dapr/{repository}"
    loader_command = " && ".join(
        [
            "mkdir -p /dapr/components /dapr/config",
            (
                f"aws s3 cp s3://{runtime_config_bucket}/{config_prefix}/components/"
                "async-events-pubsub.yaml /dapr/components/async-events-pubsub.yaml"
            ),
            (
                f"aws s3 cp s3://{runtime_config_bucket}/{config_prefix}/components/"
                "resiliency.yaml /dapr/components/resiliency.yaml"
            ),
            (
                f"aws s3 cp s3://{runtime_config_bucket}/{config_prefix}/config/"
                "config.yaml /dapr/config/config.yaml"
            ),
        ]
    )

    runtime_values = _runtime_values_for_workload(
        workload,
        stack_name=stack_name,
        region=region,
        db_address=db_address,
        db_port=db_port,
        data_hub_bucket_name=f"{stack_name}-data-hub-{account_id}",
        enable_adot_sidecar=False,
    )

    return {
        "family": f"{stack_name}-{repository}",
        "requiresCompatibilities": ["FARGATE"],
        "networkMode": "awsvpc",
        "cpu": runtime_shape["cpu"],
        "memory": runtime_shape["memory"],
        "executionRoleArn": _deterministic_role_arn(
            account_id, f"{stack_name}-task-exec"
        ),
        "taskRoleArn": _deterministic_role_arn(
            account_id, f"{stack_name}-{repository}"
        ),
        "volumes": [{"name": "dapr-config"}],
        "containerDefinitions": [
            _merge_container(
                {
                    "name": "dapr-config-loader",
                    "image": os.getenv(
                        "RUNTIME_CONFIG_LOADER_IMAGE",
                        DEFAULT_RUNTIME_CONFIG_LOADER_IMAGE,
                    ),
                    "essential": False,
                    "entryPoint": ["/bin/sh", "-c"],
                    "environment": [
                        {"name": "AWS_REGION", "value": region},
                        {"name": "AWS_DEFAULT_REGION", "value": region},
                    ],
                    "command": [loader_command],
                    "mountPoints": [
                        {
                            "sourceVolume": "dapr-config",
                            "containerPath": "/dapr",
                            "readOnly": False,
                        }
                    ],
                    "logConfiguration": _log_configuration(
                        f"/ecs/{stack_name}/{repository}",
                        region,
                        "dapr-config-loader",
                    ),
                }
            ),
            _merge_container(
                {
                    "name": "daprd",
                    "image": os.getenv("DAPR_IMAGE", DEFAULT_DAPR_IMAGE),
                    "essential": True,
                    "environment": [{"name": "AWS_REGION", "value": region}],
                    "command": [
                        "./daprd",
                        "--app-id",
                        str(dapr["app_id"]),
                        "--app-port",
                        str(service_port),
                        "--dapr-http-port",
                        "3500",
                        "--resources-path",
                        "/dapr/components",
                        "--config",
                        "/dapr/config/config.yaml",
                    ],
                    "mountPoints": [
                        {
                            "sourceVolume": "dapr-config",
                            "containerPath": "/dapr",
                            "readOnly": True,
                        }
                    ],
                    "dependsOn": [
                        {
                            "containerName": "dapr-config-loader",
                            "condition": "SUCCESS",
                        }
                    ],
                    "logConfiguration": _log_configuration(
                        f"/ecs/{stack_name}/{repository}",
                        region,
                        "daprd",
                    ),
                }
            ),
            _merge_container(
                {
                    "name": repository,
                    "image": image,
                    "essential": True,
                    "portMappings": [
                        {
                            "containerPort": service_port,
                            "hostPort": service_port,
                            "protocol": "tcp",
                        }
                    ],
                    "environment": _declared_environment(workload, runtime_values),
                    "secrets": _declared_secrets(
                        workload,
                        _runtime_secrets_for_workload(
                            workload,
                            db_secret_arn=db_secret_arn,
                            primary_edge_auth_secret_arn=None,
                        ),
                    ),
                    "dependsOn": [
                        {
                            "containerName": "dapr-config-loader",
                            "condition": "SUCCESS",
                        }
                    ],
                    "healthCheck": _health_check(
                        service_port, interval=10, start_period=20
                    ),
                    "logConfiguration": _log_configuration(
                        f"/ecs/{stack_name}/{repository}",
                        region,
                        repository,
                    ),
                }
            ),
        ],
    }


def _render_liquibase(
    *,
    stack_name: str,
    region: str,
    account_id: str,
    image: str,
    db_address: str,
    db_port: int,
    db_secret_arn: str,
) -> dict[str, Any]:
    return {
        "family": f"{stack_name}-liquibase",
        "requiresCompatibilities": ["FARGATE"],
        "networkMode": "awsvpc",
        "cpu": DEFAULT_LIQUIBASE_CPU,
        "memory": DEFAULT_LIQUIBASE_MEMORY,
        "executionRoleArn": _deterministic_role_arn(
            account_id, f"{stack_name}-task-exec"
        ),
        "taskRoleArn": _deterministic_role_arn(account_id, f"{stack_name}-liquibase"),
        "containerDefinitions": [
            _merge_container(
                {
                    "name": "liquibase",
                    "image": image,
                    "essential": True,
                    "workingDirectory": "/liquibase",
                    "command": [
                        "--search-path=/liquibase",
                        "--changelog-file=changelog/db.changelog-master.yaml",
                        "update",
                    ],
                    "secrets": [
                        {
                            "name": "LIQUIBASE_COMMAND_USERNAME",
                            "valueFrom": f"{db_secret_arn}:username::",
                        },
                        {
                            "name": "LIQUIBASE_COMMAND_PASSWORD",
                            "valueFrom": f"{db_secret_arn}:password::",
                        },
                    ],
                    "environment": [
                        {
                            "name": "LIQUIBASE_COMMAND_URL",
                            "value": (
                                f"jdbc:postgresql://{db_address}:{db_port}/"
                                f"{DEFAULT_DB_NAME}"
                            ),
                        }
                    ],
                    "logConfiguration": _log_configuration(
                        f"/ecs/{stack_name}/liquibase",
                        region,
                        "liquibase",
                    ),
                }
            )
        ],
    }


def render_task_definition(
    task_family: str,
    container_name: str,
    image: str,
) -> dict[str, Any]:
    registry, stack_name, repository = _repository_from_image(image)
    if container_name != repository:
        raise RuntimeError(
            f"container {container_name} does not match image repository {repository}"
        )

    workload = _workloads_by_repository().get(container_name)
    expected_family = _expected_task_family(stack_name, workload, container_name)
    if task_family != expected_family:
        raise RuntimeError(
            f"task family {task_family} does not match expected family {expected_family}"
        )

    region = os.getenv("AWS_REGION", "eu-central-1")
    account_id = _account_id_from_registry(registry)
    database_runtime = _resolve_database_runtime(stack_name)

    if workload is None:
        return _render_liquibase(
            stack_name=stack_name,
            region=region,
            account_id=account_id,
            image=image,
            db_address=database_runtime["address"],
            db_port=database_runtime["port"],
            db_secret_arn=database_runtime["secret_arn"],
        )

    operational_class = workload_operational_class(workload)
    if operational_class == "edge-service":
        primary_edge_secret_name = os.getenv(
            "PRIMARY_EDGE_TOKEN_SECRET", f"{stack_name}/edge-token"
        )
        return _render_primary_edge(
            workload,
            stack_name=stack_name,
            region=region,
            account_id=account_id,
            image=image,
            db_address=database_runtime["address"],
            db_port=database_runtime["port"],
            db_secret_arn=database_runtime["secret_arn"],
            primary_edge_auth_secret_arn=_resolve_primary_edge_auth_secret_arn(
                primary_edge_secret_name,
                account_id=account_id,
                region=region,
            ),
            primary_edge_task_role_arn=_resolve_primary_edge_task_role_arn(
                stack_name,
                account_id=account_id,
            ),
        )

    if operational_class == "internal-service":
        if not isinstance(workload.get("dapr"), dict):
            raise RuntimeError(
                f"internal-service workload {workload['name']} must declare dapr"
            )
        return _render_internal_async_service(
            workload,
            stack_name=stack_name,
            region=region,
            account_id=account_id,
            image=image,
            db_address=database_runtime["address"],
            db_port=database_runtime["port"],
            db_secret_arn=database_runtime["secret_arn"],
        )

    if workload.get("kind") != "job":
        raise RuntimeError(f"unsupported workload renderer target {workload['name']}")

    return _render_support_job(
        workload,
        stack_name=stack_name,
        region=region,
        account_id=account_id,
        image=image,
        db_address=database_runtime["address"],
        db_port=database_runtime["port"],
        db_secret_arn=database_runtime["secret_arn"],
        task_role_arn=_deterministic_role_arn(account_id, f"{stack_name}-{repository}"),
    )


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print(
            "usage: render_ecs_task_definition.py <task-family> <container> <image> <output-json>",
            file=sys.stderr,
        )
        return 1

    _, task_family, container_name, image, output_json = argv
    rendered = render_task_definition(task_family, container_name, image)
    Path(output_json).write_text(
        json.dumps(rendered, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
