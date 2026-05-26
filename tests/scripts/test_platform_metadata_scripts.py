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
    assert rows[0]["patterns"] == "edge-service"
    assert rows[0]["use_cases"] == "http-api"
    assert rows[0]["runtime_supported"] == "local-compose,aws-ecs"
    assert rows[0]["runtime_admitted"] == "aws-ecs"
    assert rows[0]["edge_exposure"] == "public"
    assert rows[0]["edge_auth_mode"] == "static-bearer-token"
    assert rows[0]["database_pooling"] == "transaction_pool"
    assert rows[0]["async_eventing"] == "false"
    assert rows[0]["tracing"] == "true"
    assert rows[0]["verification_profile"] == "primary-edge-runtime-modes"
    assert (
        rows[0]["runtime_mode_endpoints"]
        == "read:/admin/read-mode,write:/admin/write-mode"
    )

    event_consumer = next(row for row in rows if row["name"] == "event_consumer")
    assert event_consumer["class"] == "internal-service"
    assert event_consumer["patterns"] == "internal-async-service"
    assert event_consumer["use_cases"] == "event-consumer,integration"
    assert event_consumer["service_port"] == "8081"
    assert event_consumer["async_eventing"] == "true"
    assert event_consumer["tracing"] == "false"

    data_export_job = next(row for row in rows if row["name"] == "data_export_job")
    assert data_export_job["kind"] == "job"
    assert data_export_job["patterns"] == "scheduled-job,export-job"
    assert data_export_job["use_cases"] == "data-export,scheduled-pipeline"
    assert data_export_job["runtime_supported"] == "local-compose,aws-ecs"
    assert data_export_job["runtime_admitted"] == "aws-ecs"
    assert data_export_job["trigger"] == "schedule"
    assert data_export_job["service_port"] == ""

    open_dataset_pipeline = next(
        row for row in rows if row["name"] == "open_dataset_pipeline"
    )
    assert open_dataset_pipeline["runtime_supported"] == "local-compose"
    assert open_dataset_pipeline["runtime_admitted"] == ""


def test_workload_metadata_usage_lists_capability_matrix_command() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.platform.workload_metadata"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert completed.returncode == 1
    assert "capability-matrix" in completed.stderr
    assert "use-case-matrix" in completed.stderr
    assert "implementation-matrix" in completed.stderr
    assert "adapter-seam-matrix" in completed.stderr
    assert "inventory-json" in completed.stderr
    assert "primary-edge-contract" in completed.stderr
    assert "scheduled-job-workloads" in completed.stderr


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
        expected_primary_edge["edge"]["hostname_label"],
    ]

    primary_edge_contract = json.loads(
        _run_workload_metadata("primary-edge-contract").stdout
    )
    assert primary_edge_contract == {
        "name": expected_primary_edge["name"],
        "repository": expected_primary_edge["image"]["repository"],
        "hostname_label": expected_primary_edge["edge"]["hostname_label"],
        "auth_mode": expected_primary_edge["edge"]["auth_mode"],
        "verification_profile": expected_primary_edge["verification"]["profile"],
        "runtime_mode_endpoints": expected_primary_edge["verification"][
            "runtime_mode_endpoints"
        ],
        "metrics_required_names": expected_primary_edge["metrics"]["required_names"],
    }

    internal_services = _run_workload_metadata("internal-services").stdout.splitlines()
    assert internal_services == [
        "\t".join(
            [
                workloads_by_name["event_consumer"]["name"],
                workloads_by_name["event_consumer"]["image"]["repository"],
            ]
        )
    ]

    job_workloads = _run_workload_metadata("job-workloads").stdout.splitlines()
    expected_job_workloads = [
        "\t".join([workload["name"], workload["image"]["repository"]])
        for workload in contract["workloads"]
        if workload["kind"] == "job"
    ]
    assert job_workloads == expected_job_workloads

    support_task_workloads = _run_workload_metadata(
        "support-task-workloads"
    ).stdout.splitlines()
    expected_support_task_workloads = [
        "\t".join([workload["name"], workload["image"]["repository"]])
        for workload in contract["workloads"]
        if workload["kind"] == "job" and "aws-ecs" in workload["runtime"]["admitted"]
    ]
    assert support_task_workloads == expected_support_task_workloads

    scheduled_job_workloads = _run_workload_metadata(
        "scheduled-job-workloads"
    ).stdout.splitlines()
    expected_scheduled_job_workloads = [
        "\t".join([workload["name"], workload["image"]["repository"]])
        for workload in contract["workloads"]
        if workload["kind"] == "job"
        and workload["operational"]["class"] == "scheduled-job"
        and "aws-ecs" in workload["runtime"]["admitted"]
    ]
    assert scheduled_job_workloads == expected_scheduled_job_workloads


def test_workload_metadata_use_case_matrix_reports_declared_workload_intent() -> None:
    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())
    completed = _run_workload_metadata("use-case-matrix")

    rows = list(csv.DictReader(io.StringIO(completed.stdout), delimiter="\t"))

    assert [row["name"] for row in rows] == [
        workload["name"] for workload in contract["workloads"]
    ]
    assert rows[0]["use_cases"] == "http-api"
    assert rows[0]["runtime_supported"] == "local-compose,aws-ecs"
    assert rows[0]["runtime_admitted"] == "aws-ecs"

    backfill_worker = next(row for row in rows if row["name"] == "backfill_worker")
    assert backfill_worker["kind"] == "job"
    assert backfill_worker["class"] == "operator-job"
    assert backfill_worker["use_cases"] == "data-maintenance,operator-task"


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
        workload["name"]
        for workload in contract["workloads"]
        if "aws-ecs" in workload["runtime"]["admitted"]
    }

    for workload in contract["workloads"]:
        if "aws-ecs" not in workload["runtime"]["admitted"]:
            continue
        image = workload_images[workload["name"]]
        assert image["dockerfile"] == workload["image"].get(
            "dockerfile", "platform/workload.Dockerfile"
        )
        assert image["context"] == workload["image"].get("context", ".")
        assert image["tag"] == "sha-test"
        assert image["publish_strategy"] == "push"
        assert image["build_args"]["APP_PATH"] == workload["app_path"]
        assert image["build_args"]["UV_PACKAGE"] == workload["image"]["package"]
        assert image["build_args"]["WORKLOAD_CMD"] == workload["image"]["command"]

    liquibase = next(image for image in images if image["name"] == "liquibase")
    assert liquibase["publish_strategy"] == "push"

    pgbouncer = next(image for image in images if image["name"] == "pgbouncer")
    assert pgbouncer["publish_strategy"] == "reuse-if-present"


def test_workload_metadata_inventory_json_reports_stable_center_and_seams() -> None:
    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())
    workload_patterns = json.loads(
        (ROOT / "platform" / "workload-patterns.json").read_text()
    )
    platform_inventory = json.loads(
        (ROOT / "platform" / "platform-inventory.json").read_text()
    )
    completed = _run_workload_metadata("inventory-json")
    inventory = json.loads(completed.stdout)

    assert inventory["schema_version"] == 1
    assert inventory["stable_center"]["workload_contract"] == "platform/workloads.json"
    assert inventory["stable_center"]["platform_concerns_root"] == "platform/concerns"
    assert inventory["stable_center"]["catalog_root"] == "infra/catalog"
    assert inventory["current_runtime_target"] == "aws-ecs"
    assert [target["id"] for target in inventory["runtime_targets"]] == [
        "local-compose",
        "aws-ecs",
        "managed-service-provider",
    ]
    assert inventory["workload_patterns"] == workload_patterns["patterns"]

    assert [row["name"] for row in inventory["workloads"]] == [
        workload["name"] for workload in contract["workloads"]
    ]
    assert inventory["workloads"][0]["use_cases"] == "http-api"
    assert inventory["workloads"][0]["patterns"] == "edge-service"
    assert inventory["workloads"][0]["runtime_supported"] == "local-compose,aws-ecs"
    assert any(
        row["capability"] == "relational_database"
        for row in inventory["runtime_capabilities"]
    )
    assert any(
        row["capability"] == "async_eventing" for row in inventory["adapter_seams"]
    )
    assert inventory["stable_center"] == platform_inventory["stable_center"]
    assert (
        inventory["current_runtime_target"]
        == platform_inventory["current_runtime_target"]
    )
