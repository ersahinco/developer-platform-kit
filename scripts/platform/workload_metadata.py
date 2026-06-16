from __future__ import annotations

import json
import sys

from scripts.platform.workload_read_model import build_image_matrix
from scripts.platform.workload_read_model import build_local_kubernetes_image_matrix
from scripts.platform.workload_read_model import current_runtime_capability_rows
from scripts.platform.workload_read_model import internal_service_workloads
from scripts.platform.workload_read_model import monorepo_capability_profile
from scripts.platform.workload_read_model import operator_job_workloads
from scripts.platform.workload_read_model import primary_edge_contract
from scripts.platform.workload_read_model import runtime_default_rows
from scripts.platform.workload_read_model import support_task_workloads
from scripts.platform.workload_read_model import workload_capability_rows
from scripts.platform.workload_read_model import workload_repository


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


def _print_local_kubernetes_image_matrix(args: list[str]) -> int:
    if len(args) != 1:
        print(
            "usage: python -m scripts.platform.workload_metadata "
            "local-kubernetes-image-matrix <tag>",
            file=sys.stderr,
        )
        return 1

    (tag,) = args
    print(
        json.dumps(
            build_local_kubernetes_image_matrix(tag),
            separators=(",", ":"),
        )
    )
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


def _print_monorepo_capability_profile() -> int:
    print(json.dumps(monorepo_capability_profile(), separators=(",", ":")))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(
            "usage: python -m scripts.platform.workload_metadata "
            "<primary-edge-contract|internal-services|support-task-workloads|operator-job-workloads|image-matrix|local-kubernetes-image-matrix|capability-matrix|implementation-matrix|runtime-defaults|monorepo-capability-profile>",
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
        "local-kubernetes-image-matrix": _print_local_kubernetes_image_matrix,
        "capability-matrix": lambda _args: _print_capability_matrix(),
        "implementation-matrix": lambda _args: _print_implementation_matrix(),
        "runtime-defaults": lambda _args: _print_runtime_defaults(),
        "monorepo-capability-profile": (
            lambda _args: _print_monorepo_capability_profile()
        ),
    }
    handler = handlers.get(command)
    if handler is None:
        print(f"unknown command: {command}", file=sys.stderr)
        return 1
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
