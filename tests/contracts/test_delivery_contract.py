import json
from pathlib import Path
import re
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[2]
ENV_NAME_PATTERN = re.compile(
    r'env_(?:str|int|bool|float|optional_int)\("([A-Z0-9_]+)"'
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_repository_does_not_track_generated_or_placeholder_artifacts() -> None:
    tracked_files = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    forbidden_segments = [
        "__pycache__/",
        ".pytest_cache/",
        ".ruff_cache/",
        ".venv/",
        ".terraform/",
        ".egg-info/",
        "/dist/",
        "/build/",
    ]
    forbidden_suffixes = [
        ".pyc",
        ".pyo",
        ".tmp",
        ".bak",
        ".swp",
        "~",
    ]

    offenders = [
        path
        for path in tracked_files
        if any(segment in f"{path}/" for segment in forbidden_segments)
        or any(path.endswith(suffix) for suffix in forbidden_suffixes)
    ]

    assert offenders == []

    placeholder_roots = [
        ROOT / "deploy",
        ROOT / "local",
        ROOT / "ops",
        ROOT / "security",
    ]

    for path in placeholder_roots:
        assert not path.exists()


def test_platform_root_stays_bootstrap_and_github_oidc_only() -> None:
    platform_tf = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "infra" / "platform").glob("*.tf"))
    )
    forbidden_runtime_resources = [
        'resource "aws_ecs_',
        'resource "aws_db_',
        'resource "aws_rds_',
        'resource "aws_lb"',
        'resource "aws_lb_',
        'resource "aws_ecr_',
        'resource "aws_s3_bucket"',
        'resource "aws_sqs_',
        'resource "aws_sns_',
        'resource "aws_cloudwatch_',
        'resource "aws_scheduler_',
        'resource "aws_wafv2_',
    ]

    for forbidden in forbidden_runtime_resources:
        assert forbidden not in platform_tf


def test_infra_catalog_keeps_an_explicit_extraction_map() -> None:
    catalog_readme = _read("infra/catalog/aws/README.md")
    extraction_map = _read("infra/catalog/aws/extraction-map.md")

    assert "extraction-map.md" in catalog_readme
    for expected in [
        "VPC baseline",
        "ECR repository baseline",
        "ECS cluster baseline",
        "Dapr broker backing resources",
        "Scheduled Fargate job baseline",
    ]:
        assert expected in extraction_map


def test_app_root_consumes_platform_only_through_remote_state_outputs() -> None:
    providers_tf = _read("infra/app/providers.tf")
    app_tf = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "infra" / "app").glob("*.tf"))
    )

    assert 'data "terraform_remote_state" "platform"' in providers_tf
    assert "platform = data.terraform_remote_state.platform.outputs" in providers_tf
    assert 'source  = "../platform"' not in app_tf
    assert "data.aws_vpc" not in app_tf
    assert "data.aws_subnets" not in app_tf


def test_terraform_state_uses_s3_native_lockfiles_only() -> None:
    versions_text = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in ["infra/platform/versions.tf", "infra/app/versions.tf"]
    )
    state_docs = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in [
            "Makefile",
            "docs/deployment.md",
            "infra/platform/github_actions.tf",
        ]
    )

    assert versions_text.count("use_lockfile = true") == 2
    assert "dynamodb_table" not in versions_text
    assert "terraform-locks" not in state_docs
    assert "dynamodb:" not in state_docs


def test_infra_apply_guards_app_task_definition_drift() -> None:
    workflow_text = _read(".github/workflows/infra-apply.yml")
    guard_script = _read("scripts/ci/ci_guard_infra_plan_blast_radius.sh")

    assert "allow_ecs_task_definition_changes" in workflow_text
    assert "Guard reviewed plan blast radius" in workflow_text
    assert (
        "scripts/ci/ci_guard_infra_plan_blast_radius.sh infra/app/app_plan_output.txt"
        in workflow_text
    )
    assert "aws_ecs_task_definition" in guard_script
    assert "allow-ecs-task-definition-changes" in workflow_text
    assert "app deploy ownership boundary" in guard_script


def test_workflow_inventory_stays_small_and_intentional() -> None:
    workflow_names = sorted(
        path.name for path in (ROOT / ".github" / "workflows").glob("*.yml")
    )

    assert workflow_names == [
        "app-build.yml",
        "app-deploy.yml",
        "app-rollback-drill.yml",
        "data-runtime-rollback-drill.yml",
        "infra-apply.yml",
        "infra-plan.yml",
        "security.yml",
        "semgrep.yml",
    ]


def test_workload_registry_has_pragmatic_complete_shape() -> None:
    contract = json.loads(_read("platform/workloads.json"))
    conformance = json.loads(_read("platform/runtime-conformance.json"))

    assert contract["schema_version"] == "4"
    assert conformance["schema_version"] == "1"
    assert isinstance(contract["workloads"], list)
    assert contract["workloads"]
    assert isinstance(conformance["workloads"], dict)

    for workload in contract["workloads"]:
        assert workload["name"]
        assert workload["kind"] in {"service", "job"}
        assert workload["app_path"].startswith("apps/")
        assert "operational" in workload
        assert workload["image"]["repository"]
        assert workload["image"]["package"]
        assert workload["image"]["command"]
        assert isinstance(workload["config"]["env"], list)
        assert isinstance(workload["config"]["secrets"], list)
        assert workload["traces"]["supported"] in {True, False}
        assert workload["name"] in conformance["workloads"]
        workload_conformance = conformance["workloads"][workload["name"]]

        if workload["kind"] == "service":
            assert "service" in workload
            assert workload["operational"]["class"] in {
                "edge-service",
                "internal-service",
            }
            assert workload["operational"]["exposure"] in {"public", "internal"}
            assert workload["service"]["port"] > 0
            assert "startup_timeout_seconds" in workload_conformance
        else:
            assert "job" in workload
            assert workload["operational"]["class"] in {
                "operator-job",
                "scheduled-job",
            }
            assert workload["operational"]["trigger"] in {"manual", "schedule"}
            assert "timeout_seconds" in workload_conformance


def test_workload_contract_stays_portable_and_excludes_aws_runtime_values() -> None:
    workloads_json = _read("platform/workloads.json").lower()
    forbidden_runtime_markers = [
        "arn:",
        ".amazonaws.com",
        "aws_",
        '"ecs',
        '"ecr',
        '"rds',
        '"cloudwatch',
        '"eventbridge',
        '"wafv2',
        "s3://",
    ]

    for marker in forbidden_runtime_markers:
        assert marker not in workloads_json


def test_runtime_conformance_stays_fixture_only_not_a_second_workload_spec() -> None:
    conformance = json.loads(_read("platform/runtime-conformance.json"))
    forbidden_workload_shape_keys = {
        "app_path",
        "database",
        "dapr",
        "image",
        "job",
        "kind",
        "metrics",
        "operational",
        "service",
        "traces",
    }

    for workload_name, workload_fixture in conformance["workloads"].items():
        assert workload_name
        assert forbidden_workload_shape_keys.isdisjoint(workload_fixture)


def test_delivery_workflows_use_workload_spec_as_inventory_source() -> None:
    app_build_workflow = _read(".github/workflows/app-build.yml")
    app_deploy_workflow = _read(".github/workflows/app-deploy.yml")

    assert "platform/workloads.json" in app_build_workflow
    assert "platform/workloads.json" in app_deploy_workflow
    assert '.operational.class == "edge-service"' in app_deploy_workflow
    assert (
        "for repo in app worker data-export-job order-event-consumer liquibase"
        not in (app_deploy_workflow)
    )
    assert "services=(order-event-consumer)" not in app_deploy_workflow
    assert '--service-name "${{ needs.deploy.outputs.primary_service }}"' in (
        app_deploy_workflow
    )


def test_app_build_workflow_uses_declared_workload_build_metadata() -> None:
    app_build_workflow = _read(".github/workflows/app-build.yml")

    for expected in [
        "platform/workloads.json",
        "APP_PATH: .app_path",
        "UV_PACKAGE: .image.package",
        "WORKLOAD_CMD: .image.command",
    ]:
        assert expected in app_build_workflow


def test_makefile_operator_entrypoints_use_declared_edge_service() -> None:
    makefile = _read("Makefile")

    assert "PRIMARY_EDGE_SERVICE   ?= $(shell jq -r " in makefile
    assert '.operational.class == "edge-service"' in makefile
    assert "--service $(PRIMARY_EDGE_SERVICE)" in makefile
    assert 'ECS_SERVICE="$${ECS_SERVICE:-$(PRIMARY_EDGE_SERVICE)}"' in makefile


def test_workflow_ownership_boundaries_stay_split() -> None:
    app_deploy_workflow = _read(".github/workflows/app-deploy.yml")
    infra_apply_workflow = _read(".github/workflows/infra-apply.yml")

    assert "terraform apply -auto-approve" not in app_deploy_workflow
    assert "terraform init" not in app_deploy_workflow
    assert "ci_deploy_ecs_service.sh" in app_deploy_workflow
    assert "ci_run_ecs_task.sh" in app_deploy_workflow

    assert "terraform apply -auto-approve" in infra_apply_workflow
    assert "ci_deploy_ecs_service.sh" not in infra_apply_workflow
    assert "ci_run_ecs_task.sh" not in infra_apply_workflow


def test_observability_delivery_inventory_uses_workload_spec() -> None:
    observability_delivery = _read(
        "scripts/observability/verify_observability_delivery.py"
    )
    platform_inventory = _read("scripts/observability/platform_inventory.py")

    assert "workload_contract()" in platform_inventory
    assert "def workload_log_group_suffixes()" in platform_inventory
    assert 'REQUIRED_SUPPORT_LOG_GROUP_SUFFIXES = ["liquibase", "pgbouncer"]' in (
        platform_inventory
    )
    assert "expected_log_group_suffixes" in observability_delivery
    assert "expected_log_group_names" in observability_delivery


def test_runbooks_and_drills_avoid_demo_stack_specific_literals() -> None:
    operator_docs = "\n".join(
        path.read_text(encoding="utf-8")
        for root in [ROOT / "docs" / "runbooks", ROOT / "docs" / "drills"]
        for path in sorted(root.glob("*.md"))
    )

    assert "/ecs/aws-sdlc-containers/" not in operator_docs
    assert '{stack="aws-sdlc-containers"' not in operator_docs
    assert "--region eu-central-1" not in operator_docs


def test_incident_bundle_and_deploy_verify_reduce_repo_literal_defaults() -> None:
    incident_bundle = _read("scripts/observability/incident_evidence_bundle.py")
    platform_inventory = _read("scripts/observability/platform_inventory.py")
    verify_post_deploy = _read("scripts/release/verify_post_deploy.py")

    assert (
        "from scripts.observability.platform_inventory import dapr_workload_service_name"
        in (incident_bundle)
    )
    assert 'ROOT / "platform" / "workloads.json"' in platform_inventory
    assert "def dapr_workload_service_name()" in platform_inventory
    assert "def release_alarm_names(" in platform_inventory
    assert "def incident_alarm_names(" in platform_inventory
    assert 'or os.environ.get("STACK_NAME")' in verify_post_deploy


def test_workload_registry_maps_to_real_app_files() -> None:
    contract = json.loads(_read("platform/workloads.json"))

    for workload in contract["workloads"]:
        app_path = ROOT / workload["app_path"]
        assert app_path.is_dir()
        assert (app_path / "main.py").is_file()
        assert (app_path / "config.py").is_file()
        assert (app_path / "pyproject.toml").is_file()


def test_infra_runtime_inventory_uses_workload_contract() -> None:
    contract = json.loads(_read("platform/workloads.json"))
    inventory = _read("infra/app/workload_inventory.tf")
    compute = _read("infra/app/compute_ecs.tf")
    jobs = _read("infra/app/workload_jobs.tf")
    ecr = _read("infra/app/ecr.tf")

    assert (
        'jsondecode(file("${path.module}/../../platform/workloads.json"))' in inventory
    )
    assert 'local.workload_environment["api"]' in compute
    assert 'local.workload_secrets["api"]' in compute
    assert 'local.workload_environment["backfill_worker"]' in jobs
    assert 'local.workload_environment["data_export_job"]' in jobs
    assert 'local.workload_environment["order_event_consumer"]' in jobs
    assert "for name, workload in local.workloads_by_name" in ecr

    for workload in contract["workloads"]:
        workload_name = workload["name"]
        assert f"{workload_name} = " in inventory
        assert f'local.workload_environment["{workload_name}"]' in (
            compute if workload_name == "api" else jobs
        )
        assert f'local.workload_secrets["{workload_name}"]' in (
            compute if workload_name == "api" else jobs
        )


def test_compose_build_args_and_ports_align_with_workload_spec() -> None:
    contract = json.loads(_read("platform/workloads.json"))
    compose = yaml.safe_load(_read("compose.yaml"))
    services = compose["services"]
    service_map = {
        "api": "app",
        "backfill_worker": "worker",
        "data_export_job": "data-export-job",
        "order_event_consumer": "order-event-consumer",
    }

    for workload in contract["workloads"]:
        compose_name = service_map[workload["name"]]
        compose_service = services[compose_name]
        build_args = compose_service["build"]["args"]

        assert build_args["APP_PATH"] == workload["app_path"]
        assert build_args["UV_PACKAGE"] == workload["image"]["package"]
        assert build_args["WORKLOAD_CMD"] == workload["image"]["command"]

        if workload["kind"] == "service":
            port = workload["service"]["port"]
            declared_ports = compose_service.get("ports", [])
            if declared_ports:
                assert any(str(port) in declared for declared in declared_ports)
            else:
                env = compose_service.get("environment", {})
                env_port = env.get("ORDER_EVENTS_APP_PORT")
                assert env_port is not None
                assert str(env_port) == str(port)

    order_event_workload = next(
        workload
        for workload in contract["workloads"]
        if workload["name"] == "order_event_consumer"
    )
    dapr = order_event_workload["dapr"]
    dapr_service = services["order-event-consumer-dapr"]
    order_event_service = services["order-event-consumer"]
    command = dapr_service["command"]
    env = order_event_service["environment"]
    assert command[command.index("--app-id") + 1] == dapr["app_id"]
    assert command[command.index("--app-port") + 1] == str(
        order_event_workload["service"]["port"]
    )
    assert env["ORDER_EVENTS_APP_PORT"] == str(order_event_workload["service"]["port"])
    assert env["ORDER_EVENTS_PUBSUB_NAME"] == dapr["pubsub_name"]
    assert env["ORDER_EVENTS_TOPIC"] == dapr["topic"]


def test_workload_spec_config_names_match_app_settings() -> None:
    contract = json.loads(_read("platform/workloads.json"))
    config_paths = {
        "api": ROOT / "apps" / "api" / "config.py",
        "order_event_consumer": ROOT / "apps" / "order_event_consumer" / "config.py",
        "backfill_worker": ROOT / "apps" / "backfill_worker" / "config.py",
        "data_export_job": ROOT / "apps" / "data_export_job" / "config.py",
    }
    shared_config_text = (ROOT / "packages" / "infrastructure" / "config.py").read_text(
        encoding="utf-8"
    )
    shared_names = set(ENV_NAME_PATTERN.findall(shared_config_text))

    for workload in contract["workloads"]:
        config_text = config_paths[workload["name"]].read_text(encoding="utf-8")
        discovered_names = set(ENV_NAME_PATTERN.findall(config_text))
        if "PostgresRuntimeSettings" in config_text:
            discovered_names |= shared_names
        declared_names = set(workload["config"]["env"]) | set(
            workload["config"]["secrets"]
        )
        assert declared_names == discovered_names


def test_workload_configs_share_postgres_runtime_helper() -> None:
    for workload_name in [
        "api",
        "order_event_consumer",
        "backfill_worker",
        "data_export_job",
    ]:
        config_text = (ROOT / "apps" / workload_name / "config.py").read_text(
            encoding="utf-8"
        )
        assert "PostgresRuntimeSettings" in config_text


def test_compose_workload_env_names_stay_within_declared_contract() -> None:
    contract = json.loads(_read("platform/workloads.json"))
    compose = yaml.safe_load(_read("compose.yaml"))
    services = compose["services"]
    service_map = {
        "api": "app",
        "backfill_worker": "worker",
        "data_export_job": "data-export-job",
        "order_event_consumer": "order-event-consumer",
    }

    for workload in contract["workloads"]:
        compose_name = service_map[workload["name"]]
        compose_env = set(services[compose_name].get("environment", {}).keys())
        declared_names = set(workload["config"]["env"]) | set(
            workload["config"]["secrets"]
        )
        assert compose_env.issubset(declared_names)


def test_compose_database_wiring_matches_declared_pooling_model() -> None:
    contract = json.loads(_read("platform/workloads.json"))
    compose = yaml.safe_load(_read("compose.yaml"))
    services = compose["services"]
    service_map = {
        "api": "app",
        "backfill_worker": "worker",
        "data_export_job": "data-export-job",
        "order_event_consumer": "order-event-consumer",
    }

    for workload in contract["workloads"]:
        compose_name = service_map[workload["name"]]
        env = services[compose_name].get("environment", {})
        expected_host = (
            "pgbouncer"
            if workload["database"]["pooling"] == "transaction_pool"
            else "db"
        )

        assert env["DB_HOST"] == expected_host

        for key, value in env.items():
            if key.endswith("DATABASE_URL"):
                assert f"@{expected_host}:5432/" in value


def test_runtime_conformance_uses_declared_workload_config_names() -> None:
    contract = json.loads(_read("platform/workloads.json"))
    conformance = json.loads(_read("platform/runtime-conformance.json"))["workloads"]

    for workload in contract["workloads"]:
        names = set(workload["config"]["env"]) | set(workload["config"]["secrets"])
        workload_conformance = conformance[workload["name"]]
        conformance_names = set(workload_conformance["env"]) | set(
            workload_conformance["secrets"]
        )
        assert conformance_names.issubset(names)


def test_platform_concerns_and_catalog_boundaries_exist() -> None:
    expected_paths = [
        ROOT / "platform" / "concerns" / "dapr",
        ROOT / "platform" / "concerns" / "observability",
        ROOT / "platform" / "concerns" / "security",
        ROOT / "platform" / "concerns" / "policy",
        ROOT / "platform" / "concerns" / "networking",
        ROOT / "infra" / "catalog" / "aws",
    ]

    for path in expected_paths:
        assert path.is_dir(), f"missing expected repository boundary: {path}"


def test_observability_assets_do_not_hardcode_single_stack_inventory() -> None:
    app_overview = _read(
        "platform/concerns/observability/grafana/dashboards/app-overview.json"
    )
    log_groups = _read(
        "platform/concerns/observability/grafana/dashboards/log-groups.json"
    )
    promtail = _read("platform/concerns/observability/promtail/promtail.yml")
    compose = _read("compose.yaml")

    assert '{stack=\\"$stack\\"' in app_overview
    assert 'label_values({stack=\\"$stack\\"}, environment)' in app_overview
    assert (
        'label_values({stack=\\"$stack\\", environment=\\"$environment\\"}, log_group)'
        in (log_groups)
    )
    assert (
        'label_values({stack=\\"$stack\\", environment=\\"$environment\\", log_group=~\\"$log_group\\"}, container)'
        in (log_groups)
    )
    assert "${STACK_NAME:-aws-sdlc-containers}" in promtail
    assert "-config.expand-env=true" in compose
