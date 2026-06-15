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
from scripts.platform.workload_readiness import _evidence


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
    assert rows["api"]["evidence"] == "app-deploy.yml"
    assert rows["event_consumer"]["run_workflow"] == "app-deploy.yml"
    assert rows["event_consumer"]["evidence"] == "app-deploy.yml"
    assert rows["backfill_worker"]["run_workflow"] == "data-backfill.yml"
    assert "data-backfill.yml" in rows["backfill_worker"]["evidence"]
    assert rows["data_export_job"]["run_workflow"] == "data-support-deploy.yml"
    assert rows["data_export_job"]["evidence"] == "data-support-deploy.yml"
    assert rows["operational_snapshot_job"]["run_workflow"] == (
        "operational-snapshot.yml"
    )
    assert "operational-snapshot.yml" in rows["operational_snapshot_job"]["evidence"]
    assert rows["integration_check_job"]["run_workflow"] == "not-aws-admitted"
    assert rows["integration_check_job"]["log_group"] == "not-aws-admitted"
    assert (
        "local-kubernetes-evidence-drill"
        in rows["integration_check_job"]["proof_surface"]
    )
    assert rows["integration_check_job"]["job_terminal_event"] == (
        "integration_check_succeeded"
    )
    assert rows["open_dataset_pipeline"]["run_workflow"] == "not-aws-admitted"
    assert rows["foreign_inventory_sync"]["run_workflow"] == "not-aws-admitted"
    assert rows["foreign_inventory_sync"]["evidence"] == "n/a"


def test_workload_readiness_counts_only_runtime_evidence_for_services() -> None:
    edge_workload = {
        "name": "api",
        "kind": "service",
        "operational": {"class": "edge-service"},
        "image": {"repository": "api"},
    }
    internal_workload = {
        "name": "event_consumer",
        "kind": "service",
        "operational": {"class": "internal-service"},
        "image": {"repository": "event-consumer"},
    }
    edge_workflow_texts = {
        "app-build.yml": "api release-evidence-app-build",
        "app-deploy.yml": "release-evidence-app-deploy",
    }
    app_host_set_workflow_texts = {
        "app-deploy.yml": (
            "release-evidence-app-deploy app_host_workloads --related-workload-id"
        ),
    }

    assert (
        _evidence(
            edge_workload,
            workflow_texts=edge_workflow_texts,
            aws_admitted=True,
        )
        == "app-deploy.yml"
    )
    assert (
        _evidence(
            internal_workload,
            workflow_texts=edge_workflow_texts,
            aws_admitted=True,
        )
        == "n/a"
    )
    assert (
        _evidence(
            internal_workload,
            workflow_texts=app_host_set_workflow_texts,
            aws_admitted=True,
        )
        == "app-deploy.yml"
    )


def test_workload_readiness_requires_targeted_support_evidence() -> None:
    workload = {
        "name": "data_export_job",
        "kind": "job",
        "operational": {"class": "scheduled-job"},
        "image": {"repository": "data-export-job"},
    }
    aggregate_workflow_texts = {
        "data-support-deploy.yml": (
            "release-evidence-data-support-deploy "
            "--workload-id support-tasks target_workload"
        )
    }
    targeted_workflow_texts = {
        "data-support-deploy.yml": (
            "release-evidence-data-support-deploy "
            'evidence_workload_id="${{ inputs.target_workload }}" '
            '--workload-id "$evidence_workload_id"'
        )
    }

    assert (
        _evidence(
            workload,
            workflow_texts=aggregate_workflow_texts,
            aws_admitted=True,
        )
        == "n/a"
    )
    assert (
        _evidence(
            workload,
            workflow_texts=targeted_workflow_texts,
            aws_admitted=True,
        )
        == "data-support-deploy.yml"
    )


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
    assert "run_workflow" in rows[0]


def test_workload_readiness_cli_outputs_summary_view() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_readiness.py",
            "--view",
            "summary",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    lines = completed.stdout.splitlines()
    assert lines[0].split("\t") == [
        "workload",
        "kind",
        "class",
        "local_proof",
        "aws_ecs",
        "proof_surface",
        "proof_command",
    ]
    assert "local-compose+local-kubernetes:ready" in completed.stdout
    assert "make local-kubernetes-evidence-drill" in completed.stdout
    assert "make platform-toolkit-validate-cloud" in completed.stdout


def test_workload_readiness_cli_outputs_scoped_views() -> None:
    expected_headers = {
        "local": [
            "workload",
            "kind",
            "class",
            "local_compose",
            "local_kubernetes",
            "local_kubernetes_admission",
            "service_endpoints",
            "job_terminal_event",
            "config_contract",
            "proof_surface",
        ],
        "aws": [
            "workload",
            "kind",
            "class",
            "aws_ecs_supported",
            "aws_ecs_admitted",
            "build_matrix",
            "run_workflow",
            "evidence",
            "log_group",
            "config_contract",
        ],
        "all": [
            "workload",
            "kind",
            "class",
            "local_compose",
            "local_kubernetes",
            "aws_ecs_supported",
            "aws_ecs_admitted",
            "local_kubernetes_admission",
            "proof_surface",
            "build_matrix",
            "service_endpoints",
            "job_terminal_event",
            "run_workflow",
            "evidence",
            "log_group",
            "config_contract",
        ],
    }

    for view, header in expected_headers.items():
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/platform/workload_readiness.py",
                "--view",
                view,
            ],
            check=True,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

        assert completed.stdout.splitlines()[0].split("\t") == header


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


def test_workload_readiness_check_reports_actionable_service_gaps() -> None:
    rows = [
        {
            "workload": "example_api",
            "kind": "service",
            "class": "edge-service",
            "local_compose": "yes",
            "local_kubernetes": "yes",
            "aws_ecs_supported": "yes",
            "aws_ecs_admitted": "yes",
            "local_kubernetes_admission": "ready",
            "proof_surface": "runtime-conformance,local-kubernetes-evidence-drill",
            "build_matrix": "yes",
            "service_endpoints": "missing",
            "job_terminal_event": "n/a",
            "run_workflow": "app-deploy.yml",
            "evidence": "app-deploy.yml",
            "log_group": "/ecs/<stack>/example-api",
            "config_contract": "declared",
        }
    ]

    failures = readiness_failures(rows)

    assert "example_api: local service lacks /health, /ready, or /metrics" in failures
    assert (
        "example_api: AWS-admitted service lacks /health, /ready, or /metrics"
        in failures
    )
