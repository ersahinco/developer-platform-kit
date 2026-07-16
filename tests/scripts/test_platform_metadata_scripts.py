from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _runtime_targets(workload_name: str, field: str) -> list[str]:
    support = json.loads(
        (ROOT / "platform" / "workload-runtime-support.json").read_text()
    )
    return [
        target
        for target, profile in support["targets"].items()
        if workload_name in profile[field]
    ]


def _runtime_supported(workload: dict[str, object]) -> list[str]:
    return _runtime_targets(str(workload["name"]), "supported_workloads")


def _runtime_admitted(workload: dict[str, object]) -> list[str]:
    return _runtime_targets(str(workload["name"]), "admitted_workloads")


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
        assert row["runtime_supported"] == ",".join(_runtime_supported(workload))
        assert row["runtime_admitted"] == ",".join(_runtime_admitted(workload))
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
        if workload["kind"] == "job" and "aws-ecs" in _runtime_admitted(workload)
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
        and "aws-ecs" in _runtime_admitted(workload)
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

    action_pairs = {
        (action["workflow"], action["template"])
        for lane in lanes.values()
        for action in lane["backstage_actions"]
    }
    assert action_pairs == {
        ("app-build.yml", "catalog/action-app-build.yaml"),
        ("app-deploy.yml", "catalog/action-app-deploy.yaml"),
        ("infra-plan.yml", "catalog/action-infra-plan.yaml"),
        ("infra-apply.yml", "catalog/action-infra-apply.yaml"),
        ("data-schema-apply.yml", "catalog/action-data-schema-apply.yaml"),
        ("data-runtime-switch.yml", "catalog/action-data-runtime-switch.yaml"),
        ("data-backfill.yml", "catalog/action-data-backfill.yaml"),
        ("data-support-deploy.yml", "catalog/action-data-support-deploy.yaml"),
        (
            "operational-snapshot.yml",
            "catalog/action-operational-snapshot.yaml",
        ),
    }
    assert all((ROOT / template).is_file() for _, template in action_pairs)

    integration = profile["integration_plane"]
    assert integration["front_door"] == {
        "tool": "backstage",
        "mode": "read-and-dispatch",
        "catalog_source": "catalog-info.yaml",
        "provider_credentials": "none",
    }
    assert integration["mutation_gateway"]["tool"] == "github-actions"
    assert integration["mutation_gateway"]["credential_boundary"] == (
        "GitHub environments and OIDC"
    )
    authorities = {row["concern"]: row["owner"] for row in integration["authorities"]}
    assert authorities["infrastructure and authoritative DNS"] == (
        "Terraform roots under infra/"
    )
    assert authorities["observed deployment and release correlation"] == (
        "scripts/observability/release_event.py"
    )
    edges = {row["tool"]: row for row in integration["platform_edges"]}
    assert edges["coolify"]["status"] == "bounded-experiment"
    assert edges["netbird"]["status"] == "bounded-candidate"
    assert "never authoritative public DNS" in edges["netbird"]["authority"]

    placement = profile["workload_placement"]
    assert placement["source"] == "platform/workload-runtime-support.json"
    assert (
        placement["observed_deployments_source"]
        == "scripts/observability/release_event.py"
    )
    placements = {row["workload"]: row for row in placement["workloads"]}
    assert placements["api"]["default_runtime_target"] == "aws-ecs"
    assert placements["api"]["reference_runtime_targets"] == ["hetzner-compose"]
    assert placements["booking_api"]["default_runtime_target"] is None
    assert placements["booking_api"]["reference_runtime_targets"] == ["hetzner-compose"]

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
            "platform/workload-runtime-support.json",
            "platform/runtime-defaults.json",
            "platform/platform-inventory.json",
        ],
        "runtime_realization_roots": ["infra/app", "infra/catalog"],
        "app_contract_roots": ["apps", "packages", "platform/concerns"],
        "delivery_root": ".github/workflows",
    }


def test_workload_metadata_monorepo_capability_profile_check_and_markdown() -> None:
    checked = _run_workload_metadata("monorepo-capability-profile", "--check")
    checked_profile = json.loads(checked.stdout)
    assert checked_profile["profile"] == "lean-monorepo-capabilities"

    markdown = _run_workload_metadata(
        "monorepo-capability-profile",
        "--format=markdown",
    ).stdout
    assert "# Monorepo Capability Profile" in markdown
    assert "## Delivery Lanes" in markdown
    assert "`app-build.yml`" in markdown
    assert "## Runtime Capabilities" in markdown
    assert "`relational_database`" in markdown


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
        if "aws-ecs" in _runtime_admitted(workload)
    }

    for workload in contract["workloads"]:
        if "aws-ecs" not in _runtime_admitted(workload):
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
        if "local-kubernetes" in _runtime_supported(workload)
    }
    assert set(workload_images) == set(local_kubernetes_workloads)

    primary_edges = {
        workload["name"]
        for workload in local_kubernetes_workloads.values()
        if workload["kind"] == "service"
        and workload["operational"]["class"] == "edge-service"
        and workload["operational"]["exposure"] == "public"
        and "aws-ecs" in _runtime_admitted(workload)
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
