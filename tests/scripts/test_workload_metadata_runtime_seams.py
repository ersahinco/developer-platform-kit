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


def test_workload_metadata_implementation_matrix_reports_current_runtime_seams() -> (
    None
):
    completed = _run_workload_metadata("implementation-matrix")

    rows = list(csv.DictReader(io.StringIO(completed.stdout), delimiter="\t"))

    edge_http = next(row for row in rows if row["capability"] == "edge_http")
    assert edge_http["runtime_target"] == "aws-ecs"
    assert edge_http["implementation"] == "ALB + ECS service + ACM/WAF"
    assert "infra/app/edge.tf" in edge_http["replacement_seam"]

    relational_database = next(
        row for row in rows if row["capability"] == "relational_database"
    )
    assert relational_database["runtime_target"] == "aws-ecs"
    assert relational_database["implementation"] == "RDS PostgreSQL + PgBouncer sidecar"
    assert "infra/app/database.tf" in relational_database["replacement_seam"]

    async_eventing = next(row for row in rows if row["capability"] == "async_eventing")
    assert async_eventing["runtime_target"] == "aws-ecs"
    assert (
        async_eventing["implementation"] == "SNS FIFO + SQS FIFO behind Dapr components"
    )
    assert "infra/app/messaging.tf" in async_eventing["replacement_seam"]
