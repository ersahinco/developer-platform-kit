from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

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


def workloads() -> list[dict[str, Any]]:
    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())
    values = contract.get("workloads", [])
    return values if isinstance(values, list) else []


def has_dapr_workload() -> bool:
    return any(isinstance(workload.get("dapr"), dict) for workload in workloads())


def has_data_export_job() -> bool:
    return any(workload.get("name") == "data_export_job" for workload in workloads())


def dapr_workload_service_name() -> str:
    for workload in workloads():
        if isinstance(workload.get("dapr"), dict):
            image = workload.get("image", {})
            if isinstance(image, dict) and isinstance(image.get("repository"), str):
                return image["repository"]
    return "order-event-consumer"


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
