from __future__ import annotations

import csv
import io
import json
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


def test_workload_metadata_capability_matrix_reports_declared_workloads() -> None:
    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())
    completed = _run_workload_metadata("capability-matrix")

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
    completed = _run_workload_metadata("implementation-matrix")

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


def test_workload_metadata_cli_reports_declared_workload_groups() -> None:
    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())
    workloads_by_name = {
        workload["name"]: workload for workload in contract["workloads"]
    }

    repositories = _run_workload_metadata("repositories").stdout.splitlines()
    assert repositories == [
        workload["image"]["repository"] for workload in contract["workloads"]
    ]

    primary_edge = _run_workload_metadata("primary-edge").stdout.strip().split("\t")
    expected_primary_edge = workloads_by_name["api"]
    assert primary_edge == [
        expected_primary_edge["name"],
        expected_primary_edge["image"]["repository"],
    ]

    internal_services = _run_workload_metadata("internal-services").stdout.splitlines()
    assert internal_services == [
        "\t".join(
            [
                workloads_by_name["order_event_consumer"]["name"],
                workloads_by_name["order_event_consumer"]["image"]["repository"],
            ]
        )
    ]

    job_workloads = _run_workload_metadata("job-workloads").stdout.splitlines()
    assert job_workloads == [
        "\t".join(
            [
                workloads_by_name["backfill_worker"]["name"],
                workloads_by_name["backfill_worker"]["image"]["repository"],
            ]
        ),
        "\t".join(
            [
                workloads_by_name["data_export_job"]["name"],
                workloads_by_name["data_export_job"]["image"]["repository"],
            ]
        ),
    ]


def test_workload_metadata_image_matrix_matches_declared_apps() -> None:
    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())
    completed = _run_workload_metadata("image-matrix", "sha-test", "1.24.0")
    images = json.loads(completed.stdout)

    workload_images = {
        image["name"]: image
        for image in images
        if image["name"] not in {"liquibase", "pgbouncer"}
    }
    assert set(workload_images) == {
        workload["name"] for workload in contract["workloads"]
    }

    for workload in contract["workloads"]:
        image = workload_images[workload["name"]]
        assert image["dockerfile"] == "platform/workload.Dockerfile"
        assert image["context"] == "."
        assert image["tag"] == "sha-test"
        assert image["build_args"]["APP_PATH"] == workload["app_path"]
        assert image["build_args"]["UV_PACKAGE"] == workload["image"]["package"]
        assert image["build_args"]["WORKLOAD_CMD"] == workload["image"]["command"]
        assert (ROOT / workload["app_path"] / "main.py").is_file()
        assert (ROOT / workload["app_path"] / "config.py").is_file()
        assert (ROOT / workload["app_path"] / "pyproject.toml").is_file()
