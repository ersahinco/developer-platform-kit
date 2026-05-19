from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STACK_NAME = "aws-sdlc-containers"
DEFAULT_AWS_REGION = "eu-central-1"
DEFAULT_ENVIRONMENT = "aws"

REQUIRED_SUPPORT_LOG_GROUP_SUFFIXES = ["liquibase", "pgbouncer"]
OPTIONAL_SUPPORT_LOG_GROUP_SUFFIXES = ["adot"]
DEFAULT_ALLOWED_EXTRA_STACK_LOG_GROUP_SUFFIXES = [
    "firelens",
    "grafana",
    "loki",
    "prometheus",
    "tempo",
]
DELIVERY_EVENT_TYPES = [
    "app_deploy",
    "app_rollback_drill",
    "data_runtime_rollback_drill",
    "infra_apply",
]

_RELEASE_ALARM_SUFFIXES = [
    "app-target-5xx",
    "app-target-latency",
    "app-log-errors",
    "app-log-rollback-drill-faults",
]

_INCIDENT_ONLY_ALARM_SUFFIXES = [
    "app-unhealthy-targets",
    "rds-cpu-high",
    "rds-free-storage-low",
    "rds-connections-high",
]


@lru_cache(maxsize=1)
def workload_contract() -> dict[str, Any]:
    return json.loads((ROOT / "platform" / "workloads.json").read_text())


def workloads() -> list[dict[str, Any]]:
    values = workload_contract().get("workloads", [])
    return values if isinstance(values, list) else []


@lru_cache(maxsize=1)
def workloads_by_name() -> dict[str, dict[str, Any]]:
    return {
        workload["name"]: workload
        for workload in workloads()
        if isinstance(workload.get("name"), str)
    }


def has_dapr_workload() -> bool:
    return any(isinstance(workload.get("dapr"), dict) for workload in workloads())


def has_data_export_job() -> bool:
    return "data_export_job" in workloads_by_name()


def edge_service_repository() -> str:
    for workload in workloads():
        operational = workload.get("operational", {})
        image = workload.get("image", {})
        if (
            isinstance(operational, dict)
            and operational.get("class") == "edge-service"
            and isinstance(image, dict)
            and isinstance(image.get("repository"), str)
        ):
            return image["repository"]
    return "app"


def api_trace_service_name(stack_name: str) -> str:
    return f"{stack_name}-api"


def dapr_workload_service_name() -> str:
    for workload in workloads():
        if isinstance(workload.get("dapr"), dict):
            image = workload.get("image", {})
            if isinstance(image, dict) and isinstance(image.get("repository"), str):
                return image["repository"]
    return "order-event-consumer"


@lru_cache(maxsize=1)
def workload_log_group_suffixes() -> list[str]:
    return [
        workload["image"]["repository"]
        for workload in workloads()
        if isinstance(workload.get("image"), dict)
        and isinstance(workload["image"].get("repository"), str)
    ]


def expected_log_group_suffixes() -> list[str]:
    return [*workload_log_group_suffixes(), *REQUIRED_SUPPORT_LOG_GROUP_SUFFIXES]


def expected_log_group_names(stack_name: str) -> list[str]:
    return [f"/ecs/{stack_name}/{suffix}" for suffix in expected_log_group_suffixes()]


def default_fresh_log_group_suffixes() -> list[str]:
    return [edge_service_repository(), "pgbouncer"]


def default_fresh_loki_log_group_suffixes() -> list[str]:
    return [edge_service_repository()]


def _workload_alarm_suffixes() -> list[str]:
    suffixes: list[str] = []
    if has_dapr_workload():
        suffixes.append("order-events-dlq-visible")
    if has_data_export_job():
        suffixes.extend(
            [
                "data-export-scheduler-target-errors",
                "data-export-success-missing",
            ]
        )
    return suffixes


def release_alarm_names(stack_name: str) -> list[str]:
    return [
        f"{stack_name}-{suffix}"
        for suffix in [*_RELEASE_ALARM_SUFFIXES, *_workload_alarm_suffixes()]
    ]


def incident_alarm_names(stack_name: str) -> list[str]:
    suffixes = [
        *_INCIDENT_ONLY_ALARM_SUFFIXES,
        *_RELEASE_ALARM_SUFFIXES,
        *_workload_alarm_suffixes(),
    ]
    return [f"{stack_name}-{suffix}" for suffix in suffixes]
