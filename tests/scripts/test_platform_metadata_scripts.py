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


def test_workload_metadata_capability_matrix_matches_workload_contract() -> None:
    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())
    workloads_by_name = {
        workload["name"]: workload for workload in contract["workloads"]
    }

    completed = _run_workload_metadata("capability-matrix")
    rows = list(csv.DictReader(io.StringIO(completed.stdout), delimiter="\t"))

    assert [row["name"] for row in rows] == [
        workload["name"] for workload in contract["workloads"]
    ]

    for row in rows:
        workload = workloads_by_name[row["name"]]
        assert row["kind"] == workload["kind"]
        assert row["owner"] == workload["owner"]
        assert row["class"] == workload["operational"]["class"]
        assert row["repository"] == workload["image"]["repository"]
        assert row["runtime_supported"] == ",".join(workload["runtime"]["supported"])
        assert row["runtime_admitted"] == ",".join(workload["runtime"]["admitted"])
        assert row["use_cases"] == ",".join(workload["use_cases"])


def test_workload_metadata_primary_edge_and_workload_groups_are_contract_derived() -> (
    None
):
    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())
    workloads_by_name = {
        workload["name"]: workload for workload in contract["workloads"]
    }
    expected_primary_edge = workloads_by_name["api"]

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

    support_task_workloads = _run_workload_metadata(
        "support-task-workloads"
    ).stdout.splitlines()
    expected_support_task_workloads = [
        "\t".join([workload["name"], workload["image"]["repository"]])
        for workload in contract["workloads"]
        if workload["kind"] == "job" and "aws-ecs" in workload["runtime"]["admitted"]
    ]
    assert support_task_workloads == expected_support_task_workloads

    operator_job_workloads = _run_workload_metadata(
        "operator-job-workloads"
    ).stdout.splitlines()
    expected_operator_job_workloads = [
        "\t".join([workload["name"], workload["image"]["repository"]])
        for workload in contract["workloads"]
        if workload["kind"] == "job"
        and workload["operational"]["class"] == "operator-job"
        and "aws-ecs" in workload["runtime"]["admitted"]
    ]
    assert operator_job_workloads == expected_operator_job_workloads


def test_workload_metadata_runtime_defaults_matches_runtime_defaults_contract() -> None:
    runtime_defaults = json.loads(
        (ROOT / "platform" / "runtime-defaults.json").read_text()
    )

    completed = _run_workload_metadata("runtime-defaults")
    rows = list(csv.DictReader(io.StringIO(completed.stdout), delimiter="\t"))

    assert [row["runtime_target"] for row in rows] == sorted(
        runtime_defaults["runtime_targets"]
    )
    for row in rows:
        profile = runtime_defaults["runtime_targets"][row["runtime_target"]]
        assert row["status"] == profile["status"]
        assert row["owner"] == profile["owner"]
        for area in [
            "authn",
            "authz",
            "service_identity",
            "secrets",
            "observability",
            "network",
            "ci_cd",
            "policy",
        ]:
            assert row[area] == profile["defaults"][area]["default"]


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
