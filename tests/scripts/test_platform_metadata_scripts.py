from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_workload_metadata_capability_matrix_reports_declared_workloads() -> None:
    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.platform.workload_metadata",
            "capability-matrix",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    rows = list(csv.DictReader(io.StringIO(completed.stdout), delimiter="\t"))

    assert [row["name"] for row in rows] == [
        workload["name"] for workload in contract["workloads"]
    ]
    assert rows[0]["class"] == "edge-service"
    assert rows[0]["edge_exposure"] == "public"
    assert rows[0]["database_pooling"] == "transaction_pool"
    assert rows[0]["async_eventing"] == "false"
    assert rows[0]["tracing"] == "true"

    order_event_consumer = next(
        row for row in rows if row["name"] == "order_event_consumer"
    )
    assert order_event_consumer["class"] == "internal-service"
    assert order_event_consumer["service_port"] == "8081"
    assert order_event_consumer["async_eventing"] == "true"
    assert order_event_consumer["tracing"] == "false"

    data_export_job = next(row for row in rows if row["name"] == "data_export_job")
    assert data_export_job["kind"] == "job"
    assert data_export_job["trigger"] == "schedule"
    assert data_export_job["service_port"] == ""


def test_workload_metadata_usage_lists_capability_matrix_command() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.platform.workload_metadata"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert completed.returncode == 1
    assert "capability-matrix" in completed.stderr
    assert "implementation-matrix" in completed.stderr


def test_workload_metadata_implementation_matrix_reports_current_runtime_seams() -> (
    None
):
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.platform.workload_metadata",
            "implementation-matrix",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    rows = list(csv.DictReader(io.StringIO(completed.stdout), delimiter="\t"))

    edge_http = next(row for row in rows if row["capability"] == "edge_http")
    assert edge_http["runtime_target"] == "aws-ecs"
    assert edge_http["implementation"] == "ALB + ECS service + ACM/WAF"
    assert "infra/app/edge.tf" in edge_http["replacement_seam"]

    relational_database = next(
        row for row in rows if row["capability"] == "relational_database"
    )
    assert relational_database["implementation"] == "RDS PostgreSQL + PgBouncer sidecar"
    assert "infra/app/database.tf" in relational_database["replacement_seam"]

    async_eventing = next(row for row in rows if row["capability"] == "async_eventing")
    assert (
        async_eventing["implementation"] == "SNS FIFO + SQS FIFO behind Dapr components"
    )
    assert "infra/app/messaging.tf" in async_eventing["replacement_seam"]
