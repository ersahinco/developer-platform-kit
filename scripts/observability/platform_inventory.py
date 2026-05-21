from __future__ import annotations

from functools import lru_cache
import sys
from typing import Any

from scripts.platform.workload_metadata import platform_inventory

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
    "app_build",
    "app_deploy",
    "app_rollback_drill",
    "data_runtime_rollback_drill",
    "infra_apply",
]

_EDGE_SYMPTOM_ALARM_SUFFIX_ENDINGS = [
    "target-5xx",
    "target-latency",
]

_EDGE_RELEASE_ALARM_SUFFIX_ENDINGS = [
    "target-5xx",
    "target-latency",
    "log-errors",
    "log-rollback-drill-faults",
]

_EDGE_INCIDENT_ONLY_ALARM_SUFFIX_ENDINGS = [
    "unhealthy-targets",
]

_RUNTIME_INCIDENT_ONLY_ALARM_SUFFIXES = [
    "rds-cpu-high",
    "rds-free-storage-low",
    "rds-connections-high",
]

_WORKLOAD_ALARM_SUFFIXES_BY_NAME = {
    "order_event_consumer": ["order-events-dlq-visible"],
    "data_export_job": [
        "data-export-scheduler-target-errors",
        "data-export-success-missing",
    ],
}


@lru_cache(maxsize=1)
def _platform_inventory() -> dict[str, Any]:
    return platform_inventory()


def _workload_rows() -> list[dict[str, str]]:
    rows = _platform_inventory().get("workloads", [])
    return [row for row in rows if isinstance(row, dict)]


def _workload_row_by_name(name: str) -> dict[str, str]:
    matches = [row for row in _workload_rows() if row.get("name") == name]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one workload named {name!r}, found {len(matches)}"
        )
    return matches[0]


def _edge_service_row() -> dict[str, str]:
    matches = [
        row
        for row in _workload_rows()
        if row.get("class") == "edge-service" and row.get("edge_exposure") == "public"
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one public edge-service workload, found {len(matches)}"
        )
    return matches[0]


def _primary_async_eventing_row() -> dict[str, str]:
    matches = [row for row in _workload_rows() if row.get("async_eventing") == "true"]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one async-eventing workload, found {len(matches)}"
        )
    return matches[0]


def edge_service_repository() -> str:
    return _edge_service_row().get("repository", "") or "api"


def api_trace_service_name(stack_name: str) -> str:
    return f"{stack_name}-{edge_service_repository()}"


def dapr_workload_service_name() -> str:
    return _primary_async_eventing_row().get("repository", "") or "order-event-consumer"


@lru_cache(maxsize=1)
def workload_log_group_suffixes() -> list[str]:
    return [row["repository"] for row in _workload_rows() if row.get("repository")]


def expected_log_group_suffixes() -> list[str]:
    return [*workload_log_group_suffixes(), *REQUIRED_SUPPORT_LOG_GROUP_SUFFIXES]


def expected_log_group_names(stack_name: str) -> list[str]:
    return [f"/ecs/{stack_name}/{suffix}" for suffix in expected_log_group_suffixes()]


def default_fresh_log_group_suffixes() -> list[str]:
    return [edge_service_repository(), "pgbouncer"]


def default_fresh_loki_log_group_suffixes() -> list[str]:
    return [edge_service_repository()]


def _edge_symptom_alarm_suffixes() -> list[str]:
    repository = edge_service_repository()
    return [f"{repository}-{ending}" for ending in _EDGE_SYMPTOM_ALARM_SUFFIX_ENDINGS]


def _edge_release_alarm_suffixes() -> list[str]:
    repository = edge_service_repository()
    return [f"{repository}-{ending}" for ending in _EDGE_RELEASE_ALARM_SUFFIX_ENDINGS]


def _edge_incident_only_alarm_suffixes() -> list[str]:
    repository = edge_service_repository()
    return [
        f"{repository}-{ending}" for ending in _EDGE_INCIDENT_ONLY_ALARM_SUFFIX_ENDINGS
    ]


def edge_symptom_alarm_names(stack_name: str) -> list[str]:
    return [f"{stack_name}-{suffix}" for suffix in _edge_symptom_alarm_suffixes()]


def _workload_alarm_suffixes() -> list[str]:
    present_workload_names = {
        row["name"]
        for row in _workload_rows()
        if row.get("async_eventing") == "true" or row.get("trigger") == "schedule"
    }
    return [
        suffix
        for workload_name, suffixes in _WORKLOAD_ALARM_SUFFIXES_BY_NAME.items()
        if workload_name in present_workload_names
        for suffix in suffixes
    ]


def release_alarm_names(stack_name: str) -> list[str]:
    return [
        f"{stack_name}-{suffix}"
        for suffix in [*_edge_release_alarm_suffixes(), *_workload_alarm_suffixes()]
    ]


def incident_alarm_names(stack_name: str) -> list[str]:
    suffixes = [
        *_edge_incident_only_alarm_suffixes(),
        *_RUNTIME_INCIDENT_ONLY_ALARM_SUFFIXES,
        *_edge_release_alarm_suffixes(),
        *_workload_alarm_suffixes(),
    ]
    return [f"{stack_name}-{suffix}" for suffix in suffixes]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] != "edge-symptom-alarms":
        print(
            "usage: python -m scripts.observability.platform_inventory "
            "edge-symptom-alarms <stack-name>",
            file=sys.stderr,
        )
        return 1

    _, stack_name = argv
    for alarm_name in edge_symptom_alarm_names(stack_name):
        print(alarm_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
