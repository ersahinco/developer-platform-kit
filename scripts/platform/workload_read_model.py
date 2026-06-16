from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

WORKFLOW_LANES = {
    "infra": ["infra-plan.yml", "infra-apply.yml"],
    "app": ["app-build.yml", "app-deploy.yml"],
    "data": [
        "data-schema-apply.yml",
        "data-runtime-switch.yml",
        "data-backfill.yml",
        "data-support-deploy.yml",
        "operational-snapshot.yml",
    ],
    "security": ["security.yml", "semgrep.yml"],
    "local-proof": ["local-kubernetes-contracts.yml"],
}


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


def workload_image_entry(
    workload: dict[str, Any],
    *,
    tag: str,
    publish_strategy: str,
) -> dict[str, Any]:
    return {
        "name": workload["name"],
        "repository": workload_repository(workload),
        "dockerfile": workload_image_dockerfile(workload),
        "context": workload_image_context(workload),
        "tag": tag,
        "publish_strategy": publish_strategy,
        "build_args": {
            "APP_PATH": workload["app_path"],
            "UV_PACKAGE": workload["image"]["package"],
            "WORKLOAD_CMD": workload["image"]["command"],
        },
    }


def build_image_matrix(tag: str, pgbouncer_tag: str) -> list[dict[str, Any]]:
    images = [
        workload_image_entry(workload, tag=tag, publish_strategy="push")
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


def build_local_kubernetes_image_matrix(tag: str) -> list[dict[str, Any]]:
    primary_edge_name = primary_edge_service_workload()["name"]
    images = [
        {
            **workload_image_entry(workload, tag=tag, publish_strategy="local-load"),
            "repository": f"aws-sdlc-containers-{workload_repository(workload)}",
            "primary_edge": workload["name"] == primary_edge_name,
        }
        for workload in workloads()
        if "local-kubernetes" in workload_runtime_supported(workload)
    ]
    return [
        *images,
        {
            "name": "liquibase",
            "repository": "aws-sdlc-containers-liquibase",
            "dockerfile": "db/Dockerfile",
            "context": "db",
            "tag": tag,
            "publish_strategy": "local-load",
            "primary_edge": False,
            "build_args": {},
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


def inventory_runtime_capability_rows() -> list[dict[str, str]]:
    rows = platform_inventory_document().get("runtime_capabilities", [])
    return [row for row in rows if isinstance(row, dict)]


def runtime_target_maturity() -> dict[str, str]:
    targets = runtime_defaults_document().get("runtime_targets", {})
    if not isinstance(targets, dict):
        return {}
    return {
        str(runtime_target): str(profile.get("maturity", ""))
        for runtime_target, profile in targets.items()
        if isinstance(profile, dict)
    }


def runtime_default_capability_rows() -> list[dict[str, str]]:
    targets = runtime_defaults_document().get("runtime_targets", {})
    if not isinstance(targets, dict):
        return []

    maturity_by_target = runtime_target_maturity()
    rows: list[dict[str, str]] = []
    for runtime_target, profile in targets.items():
        if not isinstance(profile, dict):
            continue
        defaults = profile.get("defaults", {})
        if not isinstance(defaults, dict):
            continue
        for area, default in defaults.items():
            if not isinstance(default, dict):
                continue
            evidence = default.get("evidence", [])
            evidence_items = [
                item for item in evidence if isinstance(item, str) and item
            ]
            rows.append(
                {
                    "capability": str(default.get("capability", "")),
                    "contract_surface": ",".join(evidence_items) or str(area),
                    "runtime_target": str(runtime_target),
                    "maturity": maturity_by_target.get(str(runtime_target), ""),
                    "implementation": str(default.get("realization", "")),
                    "replacement_seam": (
                        "platform/runtime-defaults.json + docs/runtime-defaults.md"
                    ),
                }
            )
    return rows


def current_runtime_capability_rows() -> list[dict[str, str]]:
    return [
        *runtime_default_capability_rows(),
        *inventory_runtime_capability_rows(),
    ]


def _workflow_lanes() -> list[dict[str, Any]]:
    workflow_root = ROOT / ".github" / "workflows"
    lanes: list[dict[str, Any]] = []
    for lane, workflow_names in WORKFLOW_LANES.items():
        lanes.append(
            {
                "lane": lane,
                "toolkit": "github-actions",
                "workflows": workflow_names,
                "missing_workflows": [
                    name
                    for name in workflow_names
                    if not (workflow_root / name).is_file()
                ],
            }
        )
    return lanes


def _workload_config_names(workload: dict[str, Any], key: str) -> list[str]:
    config = workload.get("config", {})
    if not isinstance(config, dict):
        return []
    values = config.get(key, [])
    return [value for value in values if isinstance(value, str)]


def _has_object_output(workload: dict[str, Any]) -> bool:
    env_names = _workload_config_names(workload, "env")
    return any(
        name.endswith("_S3_BUCKET")
        or name.endswith("_OUTPUT_BUCKET")
        or name.endswith("_OUTPUT_DIR")
        for name in env_names
    )


def _workload_infra_capabilities(workload: dict[str, Any]) -> list[str]:
    capabilities = workload_capabilities(workload)
    names = ["network_connectivity"]
    if capabilities["edge_service"]:
        names.append("edge_http")
    if workload_database(workload) is not None:
        names.append("relational_database")
    if capabilities["async_eventing"]:
        names.append("async_eventing")
    if capabilities["scheduled_execution"]:
        names.append("scheduled_execution")
    if capabilities["operator_execution"]:
        names.append("operator_job_execution")
    if _has_object_output(workload):
        names.append("object_storage")
    if capabilities["tracing"]:
        names.append("tracing")
    return names


def monorepo_capability_profile() -> dict[str, Any]:
    workload_values = workloads()
    runtime_rows = current_runtime_capability_rows()
    config_env_names = sorted(
        {
            name
            for workload in workload_values
            for name in _workload_config_names(workload, "env")
        }
    )
    secret_names = sorted(
        {
            name
            for workload in workload_values
            for name in _workload_config_names(workload, "secrets")
        }
    )

    return {
        "schema_version": "1",
        "profile": "lean-monorepo-capabilities",
        "stable_center": platform_inventory_document().get("stable_center", {}),
        "delivery_lanes": _workflow_lanes(),
        "runtime_targets": [
            {
                "runtime_target": runtime_target,
                "maturity": maturity,
            }
            for runtime_target, maturity in sorted(runtime_target_maturity().items())
        ],
        "infra_capabilities": [
            {
                "capability": row["capability"],
                "runtime_target": row["runtime_target"],
                "maturity": row["maturity"],
                "implementation": row["implementation"],
            }
            for row in sorted(
                runtime_rows,
                key=lambda value: (value["runtime_target"], value["capability"]),
            )
        ],
        "workload_contract": {
            "source": "platform/workloads.json",
            "workload_count": len(workload_values),
            "service_count": sum(
                1 for workload in workload_values if workload.get("kind") == "service"
            ),
            "job_count": sum(
                1 for workload in workload_values if workload.get("kind") == "job"
            ),
            "operational_classes": sorted(
                {
                    workload_operational_class(workload)
                    for workload in workload_values
                    if workload_operational_class(workload)
                }
            ),
            "runtime_targets": sorted(
                {
                    runtime_target
                    for workload in workload_values
                    for runtime_target in workload_runtime_supported(workload)
                    + workload_runtime_admitted(workload)
                }
            ),
        },
        "app_contract": {
            "dapr_pubsub_workloads": [
                workload["name"]
                for workload in workload_values
                if workload_capabilities(workload)["async_eventing"]
            ],
            "database_workloads": [
                workload["name"]
                for workload in workload_values
                if workload_database(workload) is not None
            ],
            "object_output_workloads": [
                workload["name"]
                for workload in workload_values
                if _has_object_output(workload)
            ],
            "metrics_workloads": [
                workload["name"]
                for workload in workload_values
                if isinstance(workload.get("metrics"), dict)
            ],
            "tracing_workloads": [
                workload["name"]
                for workload in workload_values
                if workload_capabilities(workload)["tracing"]
            ],
            "config_env_names": config_env_names,
            "secret_names": secret_names,
        },
        "workload_infra_usage": [
            {
                "workload": workload["name"],
                "capabilities": _workload_infra_capabilities(workload),
            }
            for workload in workload_values
        ],
        "lean_controls": {
            "metadata_sources": [
                "platform/workloads.json",
                "platform/runtime-defaults.json",
                "platform/platform-inventory.json",
            ],
            "runtime_realization_roots": ["infra/app", "infra/catalog"],
            "app_contract_roots": ["apps", "packages", "platform/concerns"],
            "delivery_root": ".github/workflows",
        },
    }


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
