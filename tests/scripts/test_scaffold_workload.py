from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.platform import scaffold_workload


ROOT = Path(__file__).resolve().parents[2]


def _write_minimal_repo(root: Path) -> None:
    for relative_path in [
        "compose.yaml",
        "catalog-info.yaml",
        "platform/workloads.json",
        "platform/runtime-conformance.json",
    ]:
        destination = root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text((ROOT / relative_path).read_text(), encoding="utf-8")
    for relative_dir in ["apps", "tests/apps", "catalog"]:
        (root / relative_dir).mkdir(parents=True, exist_ok=True)


def test_scaffold_patterns_are_supported_shapes_not_executable_contract_input() -> None:
    source = (ROOT / "scripts" / "platform" / "scaffold_workload.py").read_text(
        encoding="utf-8"
    )

    assert "SUPPORTED_WORKLOAD_PATTERNS" in source
    assert "workload_pattern_contract" not in source


def test_build_plan_infers_internal_async_defaults() -> None:
    args = scaffold_workload.parse_args(
        [
            "--name",
            "invoice_worker",
            "--pattern",
            "internal-async-service",
            "--use-case",
            "integration",
            "--use-case",
            "connector",
            "--service-port",
            "8090",
        ]
    )

    plan = scaffold_workload.build_plan(args)

    assert plan.kind == "service"
    assert plan.operational_class == "internal-service"
    assert plan.workload_entry["owner"] == "platform-engineering"
    assert plan.workload_entry["runtime"] == {
        "supported": ["local-compose"],
        "admitted": [],
    }
    assert plan.workload_entry["dapr"]["app_id"] == "invoice-worker"
    assert plan.workload_entry["database"]["pooling"] == "direct"
    assert plan.runtime_conformance_entry["env"]["DAPR_TOPIC"] == "invoice-worker-v1"
    assert any(
        item.path == "compose.yaml" and item.mode == "update" for item in plan.files
    )


def test_apply_scaffolds_edge_service_and_updates_repo_files(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path)

    exit_code = scaffold_workload.main(
        [
            "--root",
            str(tmp_path),
            "--name",
            "inventory_dashboard",
            "--pattern",
            "edge-service",
            "--use-case",
            "dashboard",
            "--service-port",
            "8092",
            "--extra-env",
            "FEATURE_FLAG",
            "--apply",
        ]
    )

    assert exit_code == 0

    workload_contract = json.loads(
        (tmp_path / "platform" / "workloads.json").read_text(encoding="utf-8")
    )
    runtime_conformance = json.loads(
        (tmp_path / "platform" / "runtime-conformance.json").read_text(encoding="utf-8")
    )
    compose_text = (tmp_path / "compose.yaml").read_text(encoding="utf-8")
    catalog_info = (tmp_path / "catalog-info.yaml").read_text(encoding="utf-8")

    inventory_dashboard = next(
        workload
        for workload in workload_contract["workloads"]
        if workload["name"] == "inventory_dashboard"
    )

    assert inventory_dashboard["patterns"] == ["edge-service"]
    assert inventory_dashboard["owner"] == "platform-engineering"
    assert inventory_dashboard["runtime"] == {
        "supported": ["local-compose"],
        "admitted": [],
    }
    assert inventory_dashboard["service"]["port"] == 8092
    assert (
        inventory_dashboard["verification"]["profile"] == "primary-edge-runtime-modes"
    )
    assert "FEATURE_FLAG" in inventory_dashboard["config"]["env"]
    assert (
        runtime_conformance["workloads"]["inventory_dashboard"]["env"][
            "RUNTIME_WRITE_MODE"
        ]
        == "dual"
    )
    assert "inventory-dashboard:" in compose_text
    assert "./catalog/inventory-dashboard-component.yaml" in catalog_info

    for relative_path in [
        "apps/inventory_dashboard/config.py",
        "apps/inventory_dashboard/main.py",
        "tests/apps/inventory_dashboard/test_inventory_dashboard.py",
    ]:
        source = (tmp_path / relative_path).read_text(encoding="utf-8")
        compile(source, relative_path, "exec")

    assert 'name = "aws-sdlc-containers-inventory-dashboard"' in (
        tmp_path / "apps" / "inventory_dashboard" / "pyproject.toml"
    ).read_text(encoding="utf-8")

    component_text = (
        tmp_path / "catalog" / "inventory-dashboard-component.yaml"
    ).read_text(encoding="utf-8")
    assert "owner: group:default/platform-engineering" in component_text
    assert "resource:default/runtime-target-local-compose" in component_text
    assert "resource:default/runtime-target-aws-ecs" not in component_text


def test_apply_can_opt_in_aws_runtime_admission(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path)

    exit_code = scaffold_workload.main(
        [
            "--root",
            str(tmp_path),
            "--name",
            "billing_api",
            "--pattern",
            "edge-service",
            "--use-case",
            "http-api",
            "--service-port",
            "8093",
            "--admitted-runtime",
            "aws-ecs",
            "--apply",
        ]
    )

    assert exit_code == 0

    workload_contract = json.loads(
        (tmp_path / "platform" / "workloads.json").read_text(encoding="utf-8")
    )
    billing_api = next(
        workload
        for workload in workload_contract["workloads"]
        if workload["name"] == "billing_api"
    )
    assert billing_api["owner"] == "platform-engineering"
    assert billing_api["runtime"] == {
        "supported": ["local-compose", "aws-ecs"],
        "admitted": ["aws-ecs"],
    }

    component_text = (tmp_path / "catalog" / "billing-api-component.yaml").read_text(
        encoding="utf-8"
    )
    assert "owner: group:default/platform-engineering" in component_text
    assert "resource:default/runtime-target-local-compose" in component_text
    assert "resource:default/runtime-target-aws-ecs" in component_text


def test_unknown_workload_pattern_is_rejected(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path)

    with pytest.raises(ValueError, match="unknown workload pattern"):
        scaffold_workload.build_plan(
            scaffold_workload.parse_args(
                [
                    "--root",
                    str(tmp_path),
                    "--name",
                    "warehouse_pipeline",
                    "--pattern",
                    "data-pipeline",
                    "--use-case",
                    "data-pipeline",
                ]
            )
        )

    exit_code = scaffold_workload.main(
        [
            "--root",
            str(tmp_path),
            "--name",
            "warehouse_pipeline",
            "--pattern",
            "data-pipeline",
            "--use-case",
            "data-pipeline",
            "--apply",
        ]
    )

    assert exit_code == 1
