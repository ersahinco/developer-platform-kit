from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.platform.workload_readiness import readiness_rows
from scripts.platform.workload_readiness import readiness_failures


ROOT = Path(__file__).resolve().parents[2]


def test_workload_readiness_reports_all_declared_workloads() -> None:
    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())

    rows = readiness_rows()

    assert [row["workload"] for row in rows] == [
        workload["name"] for workload in contract["workloads"]
    ]


def test_workload_readiness_shows_paved_road_surfaces() -> None:
    rows = {row["workload"]: row for row in readiness_rows()}

    assert rows["api"]["service_endpoints"] == "/health,/ready,/metrics"
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
            "local": "yes",
            "aws_ecs": "yes",
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
