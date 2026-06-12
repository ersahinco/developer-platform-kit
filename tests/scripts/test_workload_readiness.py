from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.platform.workload_readiness import readiness_rows
from scripts.platform.workload_readiness import readiness_failures
from scripts.platform.workload_readiness import addition_rows
from scripts.platform.workload_readiness import _catalog_targets
from scripts.platform.workload_readiness import _compose_service_names


ROOT = Path(__file__).resolve().parents[2]


def test_workload_readiness_reports_all_declared_workloads() -> None:
    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())

    rows = readiness_rows()

    assert [row["workload"] for row in rows] == [
        workload["name"] for workload in contract["workloads"]
    ]


def test_workload_addition_report_shows_current_wiring_surfaces() -> None:
    rows = {row["workload"]: row for row in addition_rows()}

    assert rows["api"]["app_files"] == "ok"
    assert rows["api"]["app_tests"] == "yes"
    assert rows["support_triage_llm"]["compose_service"] == "yes"
    assert rows["support_triage_llm"]["catalog_component"] == "yes"
    assert rows["support_triage_llm"]["runtime_conformance"] == "yes"


def test_workload_addition_report_reads_compose_and_catalog_shapes() -> None:
    compose_services = _compose_service_names(ROOT / "compose.yaml")
    catalog_targets = _catalog_targets(ROOT / "catalog-info.yaml")

    assert "support-triage-llm" in compose_services
    assert "catalog/support-triage-llm-component.yaml" in catalog_targets


def test_workload_readiness_shows_paved_road_surfaces() -> None:
    rows = {row["workload"]: row for row in readiness_rows()}

    assert rows["api"]["service_endpoints"] == "/health,/ready,/metrics"
    assert rows["api"]["local_compose"] == "yes"
    assert rows["api"]["local_kubernetes"] == "yes"
    assert rows["api"]["aws_ecs_supported"] == "yes"
    assert rows["api"]["aws_ecs_admitted"] == "yes"
    assert rows["api"]["local_kubernetes_admission"] == "ready"
    assert "local-kubernetes-evidence-drill" in rows["api"]["proof_surface"]
    assert "aws-ecs-evidence" in rows["api"]["proof_surface"]
    assert rows["api"]["run_workflow"] == "app-deploy.yml"
    assert "app-deploy.yml" in rows["api"]["evidence"]
    assert rows["backfill_worker"]["run_workflow"] == "data-backfill.yml"
    assert "data-backfill.yml" in rows["backfill_worker"]["evidence"]
    assert rows["operational_snapshot_job"]["run_workflow"] == (
        "operational-snapshot.yml"
    )
    assert "operational-snapshot.yml" in rows["operational_snapshot_job"]["evidence"]
    assert rows["integration_check_job"]["run_workflow"] == "local-only"
    assert rows["integration_check_job"]["job_terminal_event"] == (
        "integration_check_succeeded"
    )
    assert rows["open_dataset_pipeline"]["run_workflow"] == "local-only"
    assert rows["foreign_inventory_sync"]["run_workflow"] == "local-only"
    assert rows["foreign_inventory_sync"]["evidence"] == "n/a"


def test_workload_readiness_cli_outputs_json() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_readiness.py",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    rows = json.loads(completed.stdout)
    assert rows[0]["workload"] == "api"


def test_workload_readiness_check_passes_for_current_contract() -> None:
    assert readiness_failures(readiness_rows()) == []


def test_workload_readiness_check_reports_actionable_aws_gaps() -> None:
    rows = [
        {
            "workload": "example_job",
            "kind": "job",
            "class": "operator-job",
            "local_compose": "yes",
            "local_kubernetes": "no",
            "aws_ecs_supported": "yes",
            "aws_ecs_admitted": "yes",
            "local_kubernetes_admission": "n/a",
            "proof_surface": "runtime-conformance",
            "build_matrix": "no",
            "service_endpoints": "n/a",
            "job_terminal_event": "missing",
            "run_workflow": "missing",
            "evidence": "n/a",
            "log_group": "missing",
            "config_contract": "missing",
        }
    ]

    failures = readiness_failures(rows)

    assert (
        "example_job: AWS-admitted workload is missing image build coverage" in failures
    )
    assert "example_job: AWS-admitted workload lacks run workflow" in failures
    assert "example_job: AWS-admitted workload lacks evidence surface" in failures
