from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


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


def workload_repository(workload: dict[str, Any]) -> str:
    image = workload.get("image", {})
    return image["repository"] if isinstance(image, dict) else ""


def workload_operational_class(workload: dict[str, Any]) -> str:
    operational = workload.get("operational", {})
    return operational.get("class", "") if isinstance(operational, dict) else ""


def build_image_matrix(tag: str, pgbouncer_tag: str) -> list[dict[str, Any]]:
    images = [
        {
            "name": workload["name"],
            "repository": workload_repository(workload),
            "dockerfile": "platform/workload.Dockerfile",
            "context": ".",
            "tag": tag,
            "build_args": {
                "APP_PATH": workload["app_path"],
                "UV_PACKAGE": workload["image"]["package"],
                "WORKLOAD_CMD": workload["image"]["command"],
            },
        }
        for workload in workloads()
    ]
    return [
        *images,
        {
            "name": "liquibase",
            "repository": "liquibase",
            "dockerfile": "db/Dockerfile",
            "context": "db",
            "tag": tag,
            "build_args": {},
        },
        {
            "name": "pgbouncer",
            "repository": "pgbouncer",
            "dockerfile": "db/pgbouncer/Dockerfile",
            "context": "db/pgbouncer",
            "tag": pgbouncer_tag,
            "build_args": {"PGBOUNCER_TAG": pgbouncer_tag},
        },
    ]


def workload_capabilities(workload: dict[str, Any]) -> dict[str, Any]:
    operational = workload.get("operational", {})
    database = workload.get("database", {})
    traces = workload.get("traces", {})

    return {
        "edge_exposure": operational.get("exposure")
        if isinstance(operational, dict)
        else None,
        "edge_service": workload.get("kind") == "service"
        and isinstance(operational, dict)
        and operational.get("class") == "edge-service",
        "internal_service": workload.get("kind") == "service"
        and isinstance(operational, dict)
        and operational.get("class") == "internal-service",
        "scheduled_execution": workload.get("kind") == "job"
        and isinstance(operational, dict)
        and operational.get("class") == "scheduled-job",
        "operator_execution": workload.get("kind") == "job"
        and isinstance(operational, dict)
        and operational.get("class") == "operator-job",
        "async_eventing": isinstance(workload.get("dapr"), dict),
        "pooled_database": isinstance(database, dict)
        and database.get("pooling") == "transaction_pool",
        "direct_database": isinstance(database, dict)
        and database.get("pooling") == "direct",
        "tracing": isinstance(traces, dict) and traces.get("supported") is True,
    }


def workload_capability_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for workload in workloads():
        operational = workload.get("operational", {})
        database = workload.get("database", {})
        service = workload.get("service", {})
        capabilities = workload_capabilities(workload)
        rows.append(
            {
                "name": str(workload.get("name", "")),
                "kind": str(workload.get("kind", "")),
                "class": workload_operational_class(workload),
                "repository": workload_repository(workload),
                "edge_exposure": (
                    str(operational.get("exposure", ""))
                    if isinstance(operational, dict)
                    else ""
                ),
                "trigger": (
                    str(operational.get("trigger", ""))
                    if isinstance(operational, dict)
                    else ""
                ),
                "service_port": (
                    str(service.get("port", "")) if isinstance(service, dict) else ""
                ),
                "database_pooling": (
                    str(database.get("pooling", ""))
                    if isinstance(database, dict)
                    else ""
                ),
                "async_eventing": str(capabilities["async_eventing"]).lower(),
                "tracing": str(capabilities["tracing"]).lower(),
            }
        )
    return rows


def current_runtime_capability_rows() -> list[dict[str, str]]:
    return [
        {
            "capability": "edge_http",
            "contract_surface": "edge-service, /health, /ready, /metrics",
            "runtime_target": "aws-ecs",
            "implementation": "ALB + ECS service + ACM/WAF",
            "replacement_seam": "infra/app/edge.tf + .github/workflows/app-deploy.yml",
        },
        {
            "capability": "relational_database",
            "contract_surface": "PostgreSQL semantics, DATABASE_URL, DB_* config names",
            "runtime_target": "aws-ecs",
            "implementation": "RDS PostgreSQL + PgBouncer sidecar",
            "replacement_seam": "infra/app/database.tf + infra/app/workload_inventory.tf",
        },
        {
            "capability": "async_eventing",
            "contract_surface": "Dapr pubsub name, topic, CloudEvents, outbox",
            "runtime_target": "aws-ecs",
            "implementation": "SNS FIFO + SQS FIFO behind Dapr components",
            "replacement_seam": "platform/concerns/dapr/ + infra/app/messaging.tf",
        },
        {
            "capability": "scheduled_execution",
            "contract_surface": "scheduled-job operational class",
            "runtime_target": "aws-ecs",
            "implementation": "EventBridge Scheduler + ECS run-task",
            "replacement_seam": "infra/app/workload_jobs.tf",
        },
        {
            "capability": "operator_job_execution",
            "contract_surface": "operator-job operational class",
            "runtime_target": "aws-ecs",
            "implementation": "manual/CI ECS run-task",
            "replacement_seam": ".github/workflows/app-deploy.yml + infra/app/workload_jobs.tf",
        },
        {
            "capability": "object_storage",
            "contract_surface": "workload config names such as DATA_EXPORT_S3_BUCKET",
            "runtime_target": "aws-ecs",
            "implementation": "S3 data hub bucket",
            "replacement_seam": "infra/app/object_storage.tf",
        },
        {
            "capability": "secrets_injection",
            "contract_surface": "declared config secrets in platform/workloads.json",
            "runtime_target": "aws-ecs",
            "implementation": "Secrets Manager + ECS secret injection",
            "replacement_seam": "infra/app/workload_inventory.tf + ECS task definitions",
        },
        {
            "capability": "tracing",
            "contract_surface": "OTLP/HTTP traces when enabled",
            "runtime_target": "aws-ecs",
            "implementation": "ADOT sidecar or direct OTLP endpoint",
            "replacement_seam": "infra/app/observability.tf + infra/app/workload_inventory.tf",
        },
        {
            "capability": "release_evidence",
            "contract_surface": "portable release-event contract",
            "runtime_target": "aws-ecs",
            "implementation": "GitHub artifact upload + optional Loki push",
            "replacement_seam": "scripts/observability/release_event.py + workflows",
        },
    ]


def internal_service_workloads() -> list[dict[str, Any]]:
    return [
        workload
        for workload in workloads()
        if workload_capabilities(workload)["internal_service"]
    ]


def job_workloads() -> list[dict[str, Any]]:
    return [workload for workload in workloads() if workload.get("kind") == "job"]


def async_eventing_workloads() -> list[dict[str, Any]]:
    return [
        workload
        for workload in workloads()
        if workload_capabilities(workload)["async_eventing"]
    ]


def scheduled_job_workloads() -> list[dict[str, Any]]:
    return [
        workload
        for workload in workloads()
        if workload_capabilities(workload)["scheduled_execution"]
    ]


def primary_async_eventing_workload() -> dict[str, Any]:
    matches = async_eventing_workloads()
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one async-eventing workload, found {len(matches)}"
        )
    return matches[0]


def primary_edge_service_workload() -> dict[str, Any]:
    matches = [
        workload
        for workload in workloads()
        if workload_capabilities(workload)["edge_service"]
        and workload_capabilities(workload)["edge_exposure"] == "public"
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one public edge-service workload, found {len(matches)}"
        )
    return matches[0]


def _print_repositories() -> int:
    for workload in workloads():
        print(workload_repository(workload))
    return 0


def _print_primary_edge() -> int:
    workload = primary_edge_service_workload()
    print(f"{workload['name']}\t{workload_repository(workload)}")
    return 0


def _print_internal_services() -> int:
    for workload in internal_service_workloads():
        print(f"{workload['name']}\t{workload_repository(workload)}")
    return 0


def _print_job_workloads() -> int:
    for workload in job_workloads():
        print(f"{workload['name']}\t{workload_repository(workload)}")
    return 0


def _print_image_matrix(args: list[str]) -> int:
    if len(args) != 2:
        print(
            "usage: python -m scripts.platform.workload_metadata image-matrix "
            "<tag> <pgbouncer-tag>",
            file=sys.stderr,
        )
        return 1

    tag, pgbouncer_tag = args
    print(json.dumps(build_image_matrix(tag, pgbouncer_tag), separators=(",", ":")))
    return 0


def _print_capability_matrix() -> int:
    headers = [
        "name",
        "kind",
        "class",
        "repository",
        "edge_exposure",
        "trigger",
        "service_port",
        "database_pooling",
        "async_eventing",
        "tracing",
    ]
    print("\t".join(headers))
    for row in workload_capability_rows():
        print("\t".join(row[header] for header in headers))
    return 0


def _print_implementation_matrix() -> int:
    headers = [
        "capability",
        "contract_surface",
        "runtime_target",
        "implementation",
        "replacement_seam",
    ]
    print("\t".join(headers))
    for row in current_runtime_capability_rows():
        print("\t".join(row[header] for header in headers))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(
            "usage: python -m scripts.platform.workload_metadata "
            "<repositories|primary-edge|internal-services|job-workloads|image-matrix|capability-matrix|implementation-matrix>",
            file=sys.stderr,
        )
        return 1

    command, *args = argv
    handlers = {
        "repositories": lambda _args: _print_repositories(),
        "primary-edge": lambda _args: _print_primary_edge(),
        "internal-services": lambda _args: _print_internal_services(),
        "job-workloads": lambda _args: _print_job_workloads(),
        "image-matrix": _print_image_matrix,
        "capability-matrix": lambda _args: _print_capability_matrix(),
        "implementation-matrix": lambda _args: _print_implementation_matrix(),
    }
    handler = handlers.get(command)
    if handler is None:
        print(f"unknown command: {command}", file=sys.stderr)
        return 1
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
