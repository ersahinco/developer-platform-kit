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
def runtime_defaults_document() -> dict[str, Any]:
    return json.loads((ROOT / "platform" / "runtime-defaults.json").read_text())


def workloads() -> list[dict[str, Any]]:
    values = workload_contract().get("workloads", [])
    return values if isinstance(values, list) else []


def workload_repository(workload: dict[str, Any]) -> str:
    image = workload.get("image", {})
    return image["repository"] if isinstance(image, dict) else ""


def workload_owner(workload: dict[str, Any]) -> str:
    owner = workload.get("owner")
    return owner if isinstance(owner, str) else ""


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


def workload_runtime_supported(workload: dict[str, Any]) -> list[str]:
    runtime = workload.get("runtime", {})
    values = runtime.get("supported", []) if isinstance(runtime, dict) else []
    return [value for value in values if isinstance(value, str)]


def workload_runtime_admitted(workload: dict[str, Any]) -> list[str]:
    runtime = workload.get("runtime", {})
    values = runtime.get("admitted", []) if isinstance(runtime, dict) else []
    return [value for value in values if isinstance(value, str)]


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
    operational_value = workload.get("operational", {})
    operational = operational_value if isinstance(operational_value, dict) else {}
    database = workload_database(workload)
    traces = workload.get("traces", {})

    return {
        "edge_exposure": operational.get("exposure"),
        "edge_service": workload.get("kind") == "service"
        and operational.get("class") == "edge-service",
        "internal_service": workload.get("kind") == "service"
        and operational.get("class") == "internal-service",
        "scheduled_execution": workload.get("kind") == "job"
        and operational.get("class") == "scheduled-job",
        "operator_execution": workload.get("kind") == "job"
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
        operational_value = workload.get("operational", {})
        operational = operational_value if isinstance(operational_value, dict) else {}
        database = workload_database(workload)
        service_value = workload.get("service", {})
        service = service_value if isinstance(service_value, dict) else {}
        capabilities = workload_capabilities(workload)
        rows.append(
            {
                "name": str(workload.get("name", "")),
                "kind": str(workload.get("kind", "")),
                "owner": workload_owner(workload),
                "class": workload_operational_class(workload),
                "use_cases": ",".join(workload_use_cases(workload)),
                "runtime_supported": ",".join(workload_runtime_supported(workload)),
                "runtime_admitted": ",".join(workload_runtime_admitted(workload)),
                "repository": workload_repository(workload),
                "edge_exposure": str(operational.get("exposure", "")),
                "edge_auth_mode": workload_edge_auth_mode(workload),
                "trigger": str(operational.get("trigger", "")),
                "service_port": str(service.get("port", "")),
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


def runtime_default_rows() -> list[dict[str, str]]:
    targets = runtime_defaults_document().get("runtime_targets", {})
    if not isinstance(targets, dict):
        return []
    rows: list[dict[str, str]] = []
    for runtime_target, profile in sorted(targets.items()):
        if not isinstance(profile, dict):
            continue
        defaults = profile.get("defaults", {})
        if not isinstance(defaults, dict):
            continue
        rows.append(
            {
                "runtime_target": str(runtime_target),
                "status": str(profile.get("status", "")),
                "owner": str(profile.get("owner", "")),
                "authn": str(_nested_default(defaults, "authn")),
                "authz": str(_nested_default(defaults, "authz")),
                "service_identity": str(_nested_default(defaults, "service_identity")),
                "secrets": str(_nested_default(defaults, "secrets")),
                "observability": str(_nested_default(defaults, "observability")),
                "network": str(_nested_default(defaults, "network")),
                "ci_cd": str(_nested_default(defaults, "ci_cd")),
                "policy": str(_nested_default(defaults, "policy")),
            }
        )
    return rows


def _nested_default(defaults: dict[str, Any], area: str) -> str:
    value = defaults.get(area, {})
    if not isinstance(value, dict):
        return ""
    default = value.get("default")
    return default if isinstance(default, str) else ""


def internal_service_workloads() -> list[dict[str, Any]]:
    return [
        workload
        for workload in workloads()
        if workload_capabilities(workload)["internal_service"]
        and workload_admitted_to_runtime(workload, "aws-ecs")
    ]


def support_task_workloads() -> list[dict[str, Any]]:
    return [
        workload
        for workload in workloads()
        if workload.get("kind") == "job"
        if workload_admitted_to_runtime(workload, "aws-ecs")
    ]


def operator_job_workloads() -> list[dict[str, Any]]:
    return [
        workload
        for workload in workloads()
        if workload_capabilities(workload)["operator_execution"]
        and workload_admitted_to_runtime(workload, "aws-ecs")
    ]


def async_eventing_workloads() -> list[dict[str, Any]]:
    return [
        workload
        for workload in workloads()
        if workload_capabilities(workload)["async_eventing"]
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


def _print_primary_edge_contract() -> int:
    print(json.dumps(primary_edge_contract(), separators=(",", ":")))
    return 0


def _print_internal_services() -> int:
    for workload in internal_service_workloads():
        print(f"{workload['name']}\t{workload_repository(workload)}")
    return 0


def _print_support_task_workloads() -> int:
    for workload in support_task_workloads():
        print(f"{workload['name']}\t{workload_repository(workload)}")
    return 0


def _print_operator_job_workloads() -> int:
    for workload in operator_job_workloads():
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
        "owner",
        "class",
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


def _print_implementation_matrix() -> int:
    headers = [
        "capability",
        "contract_surface",
        "runtime_target",
        "maturity",
        "implementation",
        "replacement_seam",
    ]
    print("\t".join(headers))
    for row in current_runtime_capability_rows():
        print("\t".join(row[header] for header in headers))
    return 0


def _print_runtime_defaults() -> int:
    headers = [
        "runtime_target",
        "status",
        "owner",
        "authn",
        "authz",
        "service_identity",
        "secrets",
        "observability",
        "network",
        "ci_cd",
        "policy",
    ]
    print("\t".join(headers))
    for row in runtime_default_rows():
        print("\t".join(row[header] for header in headers))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(
            "usage: python -m scripts.platform.workload_metadata "
            "<primary-edge-contract|internal-services|support-task-workloads|operator-job-workloads|image-matrix|capability-matrix|implementation-matrix|runtime-defaults>",
            file=sys.stderr,
        )
        return 1

    command, *args = argv
    handlers = {
        "primary-edge-contract": lambda _args: _print_primary_edge_contract(),
        "internal-services": lambda _args: _print_internal_services(),
        "support-task-workloads": lambda _args: _print_support_task_workloads(),
        "operator-job-workloads": lambda _args: _print_operator_job_workloads(),
        "image-matrix": _print_image_matrix,
        "capability-matrix": lambda _args: _print_capability_matrix(),
        "implementation-matrix": lambda _args: _print_implementation_matrix(),
        "runtime-defaults": lambda _args: _print_runtime_defaults(),
    }
    handler = handlers.get(command)
    if handler is None:
        print(f"unknown command: {command}", file=sys.stderr)
        return 1
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
