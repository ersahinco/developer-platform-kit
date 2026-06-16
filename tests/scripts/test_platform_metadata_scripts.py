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


def test_workload_metadata_implementation_matrix_derives_runtime_defaults() -> None:
    runtime_defaults = json.loads(
        (ROOT / "platform" / "runtime-defaults.json").read_text()
    )
    inventory = json.loads((ROOT / "platform" / "platform-inventory.json").read_text())

    completed = _run_workload_metadata("implementation-matrix")
    rows = list(csv.DictReader(io.StringIO(completed.stdout), delimiter="\t"))
    rows_by_pair = {(row["runtime_target"], row["capability"]): row for row in rows}

    assert len(rows_by_pair) == len(rows)

    for runtime_target, profile in runtime_defaults["runtime_targets"].items():
        for default in profile["defaults"].values():
            pair = (runtime_target, default["capability"])
            row = rows_by_pair[pair]
            assert row["implementation"] == default["realization"]
            assert row["replacement_seam"] == (
                "platform/runtime-defaults.json + docs/runtime-defaults.md"
            )

    for capability in inventory["runtime_capabilities"]:
        pair = (capability["runtime_target"], capability["capability"])
        assert rows_by_pair[pair] == capability


def test_workload_metadata_monorepo_capability_profile_is_derived() -> None:
    completed = _run_workload_metadata("monorepo-capability-profile")
    profile = json.loads(completed.stdout)

    assert profile["schema_version"] == "1"
    assert profile["profile"] == "lean-monorepo-capabilities"
    assert profile["stable_center"] == {
        "workload_contract": "platform/workloads.json",
        "platform_concerns_root": "platform/concerns",
        "catalog_root": "infra/catalog",
    }

    lanes = {lane["lane"]: lane for lane in profile["delivery_lanes"]}
    assert {"infra", "app", "data"}.issubset(lanes)
    for lane in lanes.values():
        assert lane["toolkit"] == "github-actions"
        assert lane["missing_workflows"] == []
        for workflow in lane["workflows"]:
            assert (ROOT / ".github" / "workflows" / workflow).is_file()

    capability_names = {row["capability"] for row in profile["infra_capabilities"]}
    assert {
        "network_connectivity",
        "relational_database",
        "object_storage",
        "async_eventing",
        "scheduled_execution",
        "operator_job_execution",
        "ci_cd_delivery",
    }.issubset(capability_names)

    app_contract = profile["app_contract"]
    assert "event_consumer" in app_contract["dapr_pubsub_workloads"]
    assert "api" in app_contract["database_workloads"]
    assert "data_export_job" in app_contract["object_output_workloads"]
    assert "DATABASE_URL" in app_contract["config_env_names"]
    assert "DB_PASSWORD" in app_contract["secret_names"]

    workload_usage = {
        row["workload"]: set(row["capabilities"])
        for row in profile["workload_infra_usage"]
    }
    assert {"edge_http", "relational_database", "tracing"}.issubset(
        workload_usage["api"]
    )
    assert {"async_eventing", "relational_database"}.issubset(
        workload_usage["event_consumer"]
    )
    assert {"scheduled_execution", "object_storage"}.issubset(
        workload_usage["data_export_job"]
    )

    assert profile["lean_controls"] == {
        "metadata_sources": [
            "platform/workloads.json",
            "platform/runtime-defaults.json",
            "platform/platform-inventory.json",
        ],
        "runtime_realization_roots": ["infra/app", "infra/catalog"],
        "app_contract_roots": ["apps", "packages", "platform/concerns"],
        "delivery_root": ".github/workflows",
    }


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


def test_workload_metadata_local_kubernetes_image_matrix_matches_supported_workloads() -> (
    None
):
    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())
    completed = _run_workload_metadata(
        "local-kubernetes-image-matrix",
        "local-kubernetes-test",
    )
    images = json.loads(completed.stdout)

    workload_images = {
        image["name"]: image for image in images if image["name"] != "liquibase"
    }
    local_kubernetes_workloads = {
        workload["name"]: workload
        for workload in contract["workloads"]
        if "local-kubernetes" in workload["runtime"]["supported"]
    }
    assert set(workload_images) == set(local_kubernetes_workloads)

    primary_edges = {
        workload["name"]
        for workload in local_kubernetes_workloads.values()
        if workload["kind"] == "service"
        and workload["operational"]["class"] == "edge-service"
        and workload["operational"]["exposure"] == "public"
        and "aws-ecs" in workload["runtime"]["admitted"]
    }
    assert {
        image["name"] for image in workload_images.values() if image["primary_edge"]
    } == primary_edges

    for workload_name, workload in local_kubernetes_workloads.items():
        image = workload_images[workload_name]
        assert image["repository"] == (
            f"aws-sdlc-containers-{workload['image']['repository']}"
        )
        assert image["dockerfile"] == workload["image"].get(
            "dockerfile", "platform/workload.Dockerfile"
        )
        assert image["context"] == workload["image"].get("context", ".")
        assert image["tag"] == "local-kubernetes-test"
        assert image["publish_strategy"] == "local-load"
        assert image["build_args"]["APP_PATH"] == workload["app_path"]
        assert image["build_args"]["UV_PACKAGE"] == workload["image"]["package"]
        assert image["build_args"]["WORKLOAD_CMD"] == workload["image"]["command"]

    liquibase = next(image for image in images if image["name"] == "liquibase")
    assert liquibase == {
        "name": "liquibase",
        "repository": "aws-sdlc-containers-liquibase",
        "dockerfile": "db/Dockerfile",
        "context": "db",
        "tag": "local-kubernetes-test",
        "publish_strategy": "local-load",
        "primary_edge": False,
        "build_args": {},
    }
