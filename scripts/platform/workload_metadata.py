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


@lru_cache(maxsize=1)
def platform_inventory_document() -> dict[str, Any]:
    return json.loads((ROOT / "platform" / "platform-inventory.json").read_text())


@lru_cache(maxsize=1)
def workload_pattern_contract() -> dict[str, Any]:
    return json.loads((ROOT / "platform" / "workload-patterns.json").read_text())


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


def workload_image_dockerfile(workload: dict[str, Any]) -> str:
    image = workload.get("image", {})
    if not isinstance(image, dict):
        return "platform/workload.Dockerfile"
    return str(image.get("dockerfile", "platform/workload.Dockerfile"))


def workload_image_context(workload: dict[str, Any]) -> str:
    image = workload.get("image", {})
    if not isinstance(image, dict):
        return "."
    return str(image.get("context", "."))


def workload_operational_class(workload: dict[str, Any]) -> str:
    operational = workload.get("operational", {})
    return operational.get("class", "") if isinstance(operational, dict) else ""


def workload_hostname_label(workload: dict[str, Any]) -> str:
    edge = workload.get("edge")
    if isinstance(edge, dict):
        hostname_label = edge.get("hostname_label")
        if isinstance(hostname_label, str) and hostname_label:
            return hostname_label
    repository = workload_repository(workload)
    if repository:
        return repository
    return str(workload.get("name", "")).replace("_", "-")


def workload_database(workload: dict[str, Any]) -> dict[str, Any] | None:
    database = workload.get("database")
    return database if isinstance(database, dict) else None


def workload_use_cases(workload: dict[str, Any]) -> list[str]:
    values = workload.get("use_cases", [])
    return [value for value in values if isinstance(value, str)]


def workload_patterns(workload: dict[str, Any]) -> list[str]:
    values = workload.get("patterns", [])
    return [value for value in values if isinstance(value, str)]


def workload_runtime_supported(workload: dict[str, Any]) -> list[str]:
    runtime = workload.get("runtime", {})
    values = runtime.get("supported", []) if isinstance(runtime, dict) else []
    return [value for value in values if isinstance(value, str)]


def workload_runtime_admitted(workload: dict[str, Any]) -> list[str]:
    runtime = workload.get("runtime", {})
    values = runtime.get("admitted", []) if isinstance(runtime, dict) else []
    return [value for value in values if isinstance(value, str)]


def workload_supports_runtime(workload: dict[str, Any], runtime_target: str) -> bool:
    return runtime_target in workload_runtime_supported(workload)


def workload_admitted_to_runtime(workload: dict[str, Any], runtime_target: str) -> bool:
    return runtime_target in workload_runtime_admitted(workload)


def workload_edge_auth_mode(workload: dict[str, Any]) -> str:
    edge = workload.get("edge", {})
    if not isinstance(edge, dict):
        return ""
    auth_mode = edge.get("auth_mode")
    return auth_mode if isinstance(auth_mode, str) else ""


def workload_verification(workload: dict[str, Any]) -> dict[str, Any] | None:
    verification = workload.get("verification")
    return verification if isinstance(verification, dict) else None


def workload_verification_profile(workload: dict[str, Any]) -> str:
    verification = workload_verification(workload)
    if not isinstance(verification, dict):
        return ""
    profile = verification.get("profile")
    return profile if isinstance(profile, str) else ""


def workload_runtime_mode_endpoints(workload: dict[str, Any]) -> dict[str, str]:
    verification = workload_verification(workload)
    if not isinstance(verification, dict):
        return {}
    endpoints = verification.get("runtime_mode_endpoints")
    if not isinstance(endpoints, dict):
        return {}
    return {
        key: value
        for key, value in endpoints.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def build_image_matrix(tag: str, pgbouncer_tag: str) -> list[dict[str, Any]]:
    images = [
        {
            "name": workload["name"],
            "repository": workload_repository(workload),
            "dockerfile": workload_image_dockerfile(workload),
            "context": workload_image_context(workload),
            "tag": tag,
            "publish_strategy": "push",
            "build_args": {
                "APP_PATH": workload["app_path"],
                "UV_PACKAGE": workload["image"]["package"],
                "WORKLOAD_CMD": workload["image"]["command"],
            },
        }
        for workload in workloads()
        if workload_admitted_to_runtime(workload, "aws-ecs")
    ]
    return [
        *images,
        {
            "name": "liquibase",
            "repository": "liquibase",
            "dockerfile": "db/Dockerfile",
            "context": "db",
            "tag": tag,
            "publish_strategy": "push",
            "build_args": {},
        },
        {
            "name": "pgbouncer",
            "repository": "pgbouncer",
            "dockerfile": "db/pgbouncer/Dockerfile",
            "context": "db/pgbouncer",
            "tag": pgbouncer_tag,
            "publish_strategy": "reuse-if-present",
            "build_args": {"PGBOUNCER_TAG": pgbouncer_tag},
        },
    ]


def workload_capabilities(workload: dict[str, Any]) -> dict[str, Any]:
    operational = workload.get("operational", {})
    database = workload_database(workload)
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
        database = workload_database(workload)
        service = workload.get("service", {})
        capabilities = workload_capabilities(workload)
        rows.append(
            {
                "name": str(workload.get("name", "")),
                "kind": str(workload.get("kind", "")),
                "class": workload_operational_class(workload),
                "patterns": ",".join(workload_patterns(workload)),
                "use_cases": ",".join(workload_use_cases(workload)),
                "runtime_supported": ",".join(workload_runtime_supported(workload)),
                "runtime_admitted": ",".join(workload_runtime_admitted(workload)),
                "repository": workload_repository(workload),
                "edge_exposure": (
                    str(operational.get("exposure", ""))
                    if isinstance(operational, dict)
                    else ""
                ),
                "edge_auth_mode": workload_edge_auth_mode(workload),
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
                "verification_profile": workload_verification_profile(workload),
                "runtime_mode_endpoints": ",".join(
                    [
                        f"{name}:{path}"
                        for name, path in sorted(
                            workload_runtime_mode_endpoints(workload).items()
                        )
                    ]
                ),
            }
        )
    return rows


def current_runtime_capability_rows() -> list[dict[str, str]]:
    rows = platform_inventory_document().get("runtime_capabilities", [])
    return [row for row in rows if isinstance(row, dict)]


def adapter_seam_rows() -> list[dict[str, str]]:
    rows = platform_inventory_document().get("adapter_seams", [])
    return [row for row in rows if isinstance(row, dict)]


def platform_inventory() -> dict[str, Any]:
    document = platform_inventory_document()
    return {
        "schema_version": int(str(document.get("schema_version", "1"))),
        "stable_center": dict(document.get("stable_center", {})),
        "current_runtime_target": str(document.get("current_runtime_target", "")),
        "runtime_targets": document.get("runtime_targets", []),
        "workload_patterns": workload_pattern_contract().get("patterns", []),
        "workloads": workload_capability_rows(),
        "runtime_capabilities": current_runtime_capability_rows(),
        "adapter_seams": adapter_seam_rows(),
    }


def internal_service_workloads() -> list[dict[str, Any]]:
    return [
        workload
        for workload in workloads()
        if workload_capabilities(workload)["internal_service"]
        and workload_admitted_to_runtime(workload, "aws-ecs")
    ]


def job_workloads() -> list[dict[str, Any]]:
    return [workload for workload in workloads() if workload.get("kind") == "job"]


def support_task_workloads() -> list[dict[str, Any]]:
    return [
        workload
        for workload in job_workloads()
        if workload_admitted_to_runtime(workload, "aws-ecs")
    ]


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
        and workload_admitted_to_runtime(workload, "aws-ecs")
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
        and workload_admitted_to_runtime(workload, "aws-ecs")
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one public edge-service workload, found {len(matches)}"
        )
    return matches[0]


def primary_edge_contract() -> dict[str, Any]:
    workload = primary_edge_service_workload()
    return {
        "name": str(workload["name"]),
        "repository": workload_repository(workload),
        "hostname_label": workload_hostname_label(workload),
        "auth_mode": workload_edge_auth_mode(workload),
        "verification_profile": workload_verification_profile(workload),
        "runtime_mode_endpoints": workload_runtime_mode_endpoints(workload),
        "metrics_required_names": workload["metrics"]["required_names"],
    }


def _print_repositories() -> int:
    for workload in workloads():
        print(workload_repository(workload))
    return 0


def _print_primary_edge() -> int:
    workload = primary_edge_service_workload()
    print(
        "\t".join(
            [
                str(workload["name"]),
                workload_repository(workload),
                workload_hostname_label(workload),
            ]
        )
    )
    return 0


def _print_primary_edge_contract() -> int:
    print(json.dumps(primary_edge_contract(), separators=(",", ":")))
    return 0


def _print_internal_services() -> int:
    for workload in internal_service_workloads():
        print(f"{workload['name']}\t{workload_repository(workload)}")
    return 0


def _print_job_workloads() -> int:
    for workload in job_workloads():
        print(f"{workload['name']}\t{workload_repository(workload)}")
    return 0


def _print_support_task_workloads() -> int:
    for workload in support_task_workloads():
        print(f"{workload['name']}\t{workload_repository(workload)}")
    return 0


def _print_scheduled_job_workloads() -> int:
    for workload in scheduled_job_workloads():
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
        "patterns",
        "use_cases",
        "runtime_supported",
        "runtime_admitted",
        "repository",
        "edge_exposure",
        "edge_auth_mode",
        "trigger",
        "service_port",
        "database_pooling",
        "async_eventing",
        "tracing",
        "verification_profile",
        "runtime_mode_endpoints",
    ]
    print("\t".join(headers))
    for row in workload_capability_rows():
        print("\t".join(row[header] for header in headers))
    return 0


def _print_use_case_matrix() -> int:
    headers = [
        "name",
        "kind",
        "class",
        "use_cases",
        "runtime_supported",
        "runtime_admitted",
        "repository",
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


def _print_adapter_seam_matrix() -> int:
    headers = [
        "capability",
        "contract_surface",
        "adapter_seam",
        "runtime_target",
        "current_implementation",
        "runtime_seam",
    ]
    print("\t".join(headers))
    for row in adapter_seam_rows():
        print("\t".join(row[header] for header in headers))
    return 0


def _print_inventory_json() -> int:
    print(json.dumps(platform_inventory(), separators=(",", ":")))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(
            "usage: python -m scripts.platform.workload_metadata "
            "<repositories|primary-edge|primary-edge-contract|internal-services|job-workloads|support-task-workloads|scheduled-job-workloads|image-matrix|capability-matrix|use-case-matrix|implementation-matrix|adapter-seam-matrix|inventory-json>",
            file=sys.stderr,
        )
        return 1

    command, *args = argv
    handlers = {
        "repositories": lambda _args: _print_repositories(),
        "primary-edge": lambda _args: _print_primary_edge(),
        "primary-edge-contract": lambda _args: _print_primary_edge_contract(),
        "internal-services": lambda _args: _print_internal_services(),
        "job-workloads": lambda _args: _print_job_workloads(),
        "support-task-workloads": lambda _args: _print_support_task_workloads(),
        "scheduled-job-workloads": lambda _args: _print_scheduled_job_workloads(),
        "image-matrix": _print_image_matrix,
        "capability-matrix": lambda _args: _print_capability_matrix(),
        "use-case-matrix": lambda _args: _print_use_case_matrix(),
        "implementation-matrix": lambda _args: _print_implementation_matrix(),
        "adapter-seam-matrix": lambda _args: _print_adapter_seam_matrix(),
        "inventory-json": lambda _args: _print_inventory_json(),
    }
    handler = handlers.get(command)
    if handler is None:
        print(f"unknown command: {command}", file=sys.stderr)
        return 1
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
