#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tomllib
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.platform.workload_metadata import build_image_matrix  # noqa: E402
from scripts.platform.workload_metadata import workload_capabilities  # noqa: E402
from scripts.platform.workload_metadata import workload_repository  # noqa: E402
from scripts.platform.workload_metadata import workload_runtime_admitted  # noqa: E402
from scripts.platform.workload_metadata import workload_runtime_supported  # noqa: E402
from scripts.platform.workload_metadata import workloads  # noqa: E402


def _runtime_conformance() -> dict[str, Any]:
    return json.loads((ROOT / "platform" / "runtime-conformance.json").read_text())


def _workflow_texts() -> dict[str, str]:
    workflow_dir = ROOT / ".github" / "workflows"
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(workflow_dir.glob("*.yml"))
    }


def _yes(value: bool) -> str:
    return "yes" if value else "no"


def _workflow_mentions(workflow_texts: dict[str, str], *needles: str) -> list[str]:
    present = []
    filtered_needles = [needle for needle in needles if needle]
    for name, text in workflow_texts.items():
        if any(needle in text for needle in filtered_needles):
            present.append(name)
    return present


def _run_workflows(
    workload: dict[str, Any],
    *,
    workflow_texts: dict[str, str],
    aws_admitted: bool,
) -> str:
    if not aws_admitted:
        return "local-only"

    capabilities = workload_capabilities(workload)
    if capabilities["edge_service"] or capabilities["internal_service"]:
        return "app-deploy.yml"
    if capabilities["scheduled_execution"]:
        return "data-support-deploy.yml"
    if capabilities["operator_execution"]:
        matches = _workflow_mentions(
            workflow_texts,
            str(workload["name"]),
            workload_repository(workload),
        )
        run_workflows = [
            workflow
            for workflow in matches
            if workflow
            not in {
                "app-build.yml",
                "data-support-deploy.yml",
                "infra-plan.yml",
                "security.yml",
            }
        ]
        return ",".join(run_workflows) if run_workflows else "missing"
    return "missing"


def _evidence(
    workload: dict[str, Any],
    *,
    workflow_texts: dict[str, str],
    aws_admitted: bool,
) -> str:
    if not aws_admitted:
        return "n/a"

    name = str(workload["name"])
    repository = workload_repository(workload)
    matches = _workflow_mentions(workflow_texts, name, repository)
    evidence_workflows = [
        workflow
        for workflow in matches
        if "release-evidence-" in workflow_texts[workflow]
        or "operator-payload-" in workflow_texts[workflow]
    ]
    capabilities = workload_capabilities(workload)
    if capabilities["edge_service"] or capabilities["internal_service"]:
        evidence_workflows.append("app-deploy.yml")
    if capabilities["scheduled_execution"]:
        evidence_workflows.append("data-support-deploy.yml")
    return ",".join(sorted(set(evidence_workflows))) if evidence_workflows else "n/a"


def _terminal_events(
    workload: dict[str, Any],
    *,
    conformance: dict[str, Any],
) -> str:
    if workload.get("kind") != "job":
        return "n/a"
    fixture = conformance.get("workloads", {}).get(workload["name"], {})
    if not isinstance(fixture, dict):
        return "missing"
    event = fixture.get("expected_success_event")
    if isinstance(event, str) and event:
        return event
    return "missing"


def _service_endpoints(workload: dict[str, Any]) -> str:
    if workload.get("kind") != "service":
        return "n/a"
    service = workload.get("service")
    metrics = workload.get("metrics")
    if isinstance(service, dict) and isinstance(metrics, dict):
        return "/health,/ready,/metrics"
    return "missing"


def _config_contract(workload: dict[str, Any]) -> str:
    config = workload.get("config")
    if not isinstance(config, dict):
        return "missing"
    env = config.get("env")
    secrets = config.get("secrets")
    if isinstance(env, list) and isinstance(secrets, list):
        return "declared"
    return "missing"


def _compose_service_names(path: Path) -> set[str]:
    services: set[str] = set()
    in_services = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line == "services:":
            in_services = True
            continue
        if in_services and not line.startswith(" "):
            break
        if in_services and line.startswith("  ") and not line.startswith("    "):
            name = line.strip().removesuffix(":")
            if name:
                services.add(name)
    return services


def _catalog_targets(path: Path) -> set[str]:
    targets: set[str] = set()
    in_targets = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "targets:":
            in_targets = True
            continue
        if in_targets and stripped.startswith("- "):
            target = stripped.removeprefix("- ").removeprefix("./")
            targets.add(target)
            continue
        if in_targets and stripped and not line.startswith(" "):
            break
    return targets


def addition_rows() -> list[dict[str, str]]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    workspace_members = set(pyproject["tool"]["uv"]["workspace"]["members"])
    dockerfile = (ROOT / "platform" / "workload.Dockerfile").read_text(encoding="utf-8")
    compose_services = _compose_service_names(ROOT / "compose.yaml")
    catalog_targets = _catalog_targets(ROOT / "catalog-info.yaml")
    conformance = _runtime_conformance().get("workloads", {})

    rows = []
    for workload in workloads():
        name = str(workload["name"])
        app_path = str(workload["app_path"])
        repository = workload_repository(workload)
        app_root = ROOT / app_path
        required_files = ["main.py", "config.py", "pyproject.toml"]
        missing_app_files = [
            filename
            for filename in required_files
            if not (app_root / filename).exists()
        ]
        catalog_path = ROOT / "catalog" / f"{repository}-component.yaml"
        rows.append(
            {
                "workload": name,
                "app_files": (
                    "ok" if not missing_app_files else ",".join(missing_app_files)
                ),
                "uv_workspace": _yes(app_path in workspace_members),
                "dockerfile_copy": _yes(
                    f"COPY {app_path}/pyproject.toml {app_path}/pyproject.toml"
                    in dockerfile
                ),
                "compose_service": _yes(repository in compose_services),
                "runtime_conformance": _yes(name in conformance),
                "catalog_component": _yes(
                    catalog_path.exists()
                    and f"catalog/{repository}-component.yaml" in catalog_targets
                ),
                "app_tests": _yes(_has_app_tests(name)),
            }
        )
    return rows


def _has_app_tests(workload_name: str) -> bool:
    if (ROOT / "tests" / "apps" / workload_name).exists():
        return True
    if workload_name == "api" and (ROOT / "tests" / "api").exists():
        return True
    return False


def readiness_rows() -> list[dict[str, str]]:
    conformance = _runtime_conformance()
    workflow_texts = _workflow_texts()
    aws_image_names = {
        image["name"]
        for image in build_image_matrix("sha-readiness", "pgbouncer-readiness")
        if image.get("name") not in {"liquibase", "pgbouncer"}
    }
    rows = []
    for workload in workloads():
        name = str(workload["name"])
        repository = workload_repository(workload)
        supported = set(workload_runtime_supported(workload))
        admitted = set(workload_runtime_admitted(workload))
        local_supported = "local-compose" in supported
        aws_admitted = "aws-ecs" in admitted
        rows.append(
            {
                "workload": name,
                "kind": str(workload.get("kind", "")),
                "class": str(workload.get("operational", {}).get("class", "")),
                "local": _yes(local_supported),
                "aws_ecs": _yes(aws_admitted),
                "build_matrix": _yes(not aws_admitted or name in aws_image_names),
                "service_endpoints": _service_endpoints(workload),
                "job_terminal_event": _terminal_events(
                    workload,
                    conformance=conformance,
                ),
                "run_workflow": _run_workflows(
                    workload,
                    workflow_texts=workflow_texts,
                    aws_admitted=aws_admitted,
                ),
                "evidence": _evidence(
                    workload,
                    workflow_texts=workflow_texts,
                    aws_admitted=aws_admitted,
                ),
                "log_group": (
                    f"/ecs/<stack>/{repository}" if aws_admitted else "local-only"
                ),
                "config_contract": _config_contract(workload),
            }
        )
    return rows


def readiness_failures(rows: list[dict[str, str]]) -> list[str]:
    failures: list[str] = []
    for row in rows:
        workload = row["workload"]

        if row["local"] == "yes":
            if row["config_contract"] != "declared":
                failures.append(f"{workload}: local workload lacks config contract")
            if row["kind"] == "service" and row["service_endpoints"] == "missing":
                failures.append(
                    f"{workload}: local service lacks /health, /ready, or /metrics"
                )
            if row["kind"] == "job" and row["job_terminal_event"] == "missing":
                failures.append(f"{workload}: local job lacks terminal success event")

        if row["aws_ecs"] != "yes":
            continue

        required_fields = {
            "build_matrix": "AWS-admitted workload is missing image build coverage",
            "config_contract": "AWS-admitted workload lacks config contract",
        }
        for field, message in required_fields.items():
            expected = "yes" if field == "build_matrix" else "declared"
            if row[field] != expected:
                failures.append(f"{workload}: {message}")

        if row["run_workflow"] in {"missing", "local-only"}:
            failures.append(f"{workload}: AWS-admitted workload lacks run workflow")
        if row["evidence"] == "n/a":
            failures.append(f"{workload}: AWS-admitted workload lacks evidence surface")
        if not row["log_group"].startswith("/ecs/<stack>/"):
            failures.append(
                f"{workload}: AWS-admitted workload lacks log group convention"
            )
        if row["kind"] == "service" and row["service_endpoints"] == "missing":
            failures.append(
                f"{workload}: AWS-admitted service lacks /health, /ready, or /metrics"
            )
        if row["kind"] == "job" and row["job_terminal_event"] == "missing":
            failures.append(
                f"{workload}: AWS-admitted job lacks terminal success event"
            )
    return failures


def _print_table(rows: list[dict[str, str]]) -> None:
    headers = [
        "workload",
        "kind",
        "class",
        "local",
        "aws_ecs",
        "build_matrix",
        "service_endpoints",
        "job_terminal_event",
        "run_workflow",
        "evidence",
        "log_group",
        "config_contract",
    ]
    print("\t".join(headers))
    for row in rows:
        print("\t".join(row[header] for header in headers))


def _print_addition_table(rows: list[dict[str, str]]) -> None:
    headers = [
        "workload",
        "app_files",
        "uv_workspace",
        "dockerfile_copy",
        "compose_service",
        "runtime_conformance",
        "catalog_component",
        "app_tests",
    ]
    print("\t".join(headers))
    for row in rows:
        print("\t".join(row[header] for header in headers))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report workload paved-road readiness from platform contracts and conventional delivery files."
    )
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when declared workloads are missing paved-road delivery surfaces.",
    )
    parser.add_argument(
        "--addition-report",
        action="store_true",
        help="Show conventional files to check when adding or reviewing workloads.",
    )
    args = parser.parse_args()

    if args.addition_report:
        rows = addition_rows()
        if args.format == "json":
            print(json.dumps(rows, sort_keys=True))
        else:
            _print_addition_table(rows)
        return 0

    rows = readiness_rows()
    if args.format == "json":
        print(json.dumps(rows, sort_keys=True))
    else:
        _print_table(rows)
    failures = readiness_failures(rows)
    if args.check and failures:
        print("\nReadiness check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
