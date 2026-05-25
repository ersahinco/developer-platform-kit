from __future__ import annotations

import csv
import io
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _run_workload_metadata(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.platform.workload_metadata", *args],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def test_workload_metadata_adapter_seam_matrix_reports_portability_seams() -> None:
    completed = _run_workload_metadata("adapter-seam-matrix")
    rows = list(csv.DictReader(io.StringIO(completed.stdout), delimiter="\t"))

    database = next(row for row in rows if row["capability"] == "relational_database")
    assert database["runtime_target"] == "aws-ecs"
    assert "packages/infrastructure/db/" in database["adapter_seam"]
    assert "infra/app/database.tf" in database["runtime_seam"]

    eventing = next(row for row in rows if row["capability"] == "async_eventing")
    assert eventing["runtime_target"] == "aws-ecs"
    assert eventing["adapter_seam"] == "packages/infrastructure/dapr/"
    assert "infra/app/messaging.tf" in eventing["runtime_seam"]

    secrets = next(
        row for row in rows if row["capability"] == "secrets_and_runtime_config"
    )
    assert secrets["runtime_target"] == "aws-ecs"
    assert "platform/workloads.json" in secrets["contract_surface"]
    assert "workload_inventory.tf" in secrets["runtime_seam"]
