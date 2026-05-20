import json
from pathlib import Path
import re
import subprocess
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
ENV_NAME_PATTERN = re.compile(
    r'env_(?:str|int|bool|float|optional_int)\("([A-Z0-9_]+)"'
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _runtime_conformance() -> dict[str, Any]:
    return json.loads(_read("platform/runtime-conformance.json"))


def _workload_conformance(
    workload: dict[str, Any], conformance: dict[str, Any]
) -> dict[str, Any]:
    defaults = conformance.get("defaults", {})
    default_env = dict(defaults.get("env", {}))  # type: ignore[union-attr]
    default_secrets = dict(defaults.get("secrets", {}))  # type: ignore[union-attr]
    workload_fixture = dict(conformance["workloads"][workload["name"]])  # type: ignore[index]
    database = workload["database"]
    default_env["DB_HOST"] = (
        "pgbouncer" if database["pooling"] == "transaction_pool" else "db"
    )
    workload_fixture["env"] = {**default_env, **dict(workload_fixture.get("env", {}))}
    workload_fixture["secrets"] = {
        **default_secrets,
        **dict(workload_fixture.get("secrets", {})),
    }
    return workload_fixture


def _compose_service_name(workload: dict[str, Any]) -> str:
    image = workload["image"]
    return str(image["repository"])


def _config_path(workload: dict[str, Any]) -> Path:
    return ROOT / str(workload["app_path"]) / "config.py"


def _workload_by_name(contract: dict[str, Any], workload_name: str) -> dict[str, Any]:
    return next(
        workload
        for workload in contract["workloads"]  # type: ignore[index]
        if workload["name"] == workload_name
    )


def _operator_surface_text() -> str:
    return "\n".join(
        [
            _read("scripts/operator/db_exec.sh"),
            _read("scripts/operator/db_tunnel.sh"),
            _read("docs/drills/app-dependency-readiness.md"),
            _read("docs/runbooks/ecs-deploy-rollback.md"),
            _read("docs/runbooks/app-service-incident.md"),
            _read("docs/runbooks/order-event-queue-failure.md"),
        ]
    )


def _alarm_surface_text() -> str:
    return "\n".join(
        [
            _read("docs/runbooks/app-service-incident.md"),
            _read("docs/runbooks/ecs-deploy-rollback.md"),
        ]
    )


def _declared_config_names(workload: dict[str, Any]) -> set[str]:
    return set(workload["config"]["env"]) | set(workload["config"]["secrets"])


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
    conformance = _runtime_conformance()

    assert contract["schema_version"] == "4"
    assert conformance["schema_version"] == "2"
    assert isinstance(contract["workloads"], list)
    assert contract["workloads"]
    assert isinstance(conformance["defaults"], dict)
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
        workload_conformance = _workload_conformance(workload, conformance)

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
    conformance = _runtime_conformance()
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

    assert set(conformance["defaults"]) == {"env", "secrets"}

    for workload_name, workload_fixture in conformance["workloads"].items():
        assert workload_name
        assert forbidden_workload_shape_keys.isdisjoint(workload_fixture)


def test_delivery_workflows_use_workload_spec_as_inventory_source() -> None:
    app_build_workflow = _read(".github/workflows/app-build.yml")
    app_deploy_workflow = _read(".github/workflows/app-deploy.yml")
    app_rollback_workflow = _read(".github/workflows/app-rollback-drill.yml")
    data_runtime_rollback_workflow = _read(
        ".github/workflows/data-runtime-rollback-drill.yml"
    )
    platform_inventory = _read("scripts/observability/platform_inventory.py")
    workload_metadata = _read("scripts/platform/workload_metadata.py")

    assert "python3 -m scripts.platform.workload_metadata image-matrix" in (
        app_build_workflow
    )
    assert "python3 -m scripts.platform.workload_metadata repositories" in (
        app_deploy_workflow
    )
    assert "python3 -m scripts.platform.workload_metadata primary-edge" in (
        app_deploy_workflow
    )
    assert "python3 -m scripts.platform.workload_metadata primary-edge" in (
        app_rollback_workflow
    )
    assert "python3 -m scripts.platform.workload_metadata primary-edge" in (
        data_runtime_rollback_workflow
    )
    assert (
        "python3 -m scripts.observability.platform_inventory edge-symptom-alarms"
        in app_rollback_workflow
    )
    assert "python3 -m scripts.platform.workload_metadata internal-services" in (
        app_deploy_workflow
    )
    assert "python3 -m scripts.platform.workload_metadata job-workloads" in (
        app_deploy_workflow
    )
    assert 'ROOT / "platform" / "workloads.json"' in workload_metadata
    assert "def workload_capabilities(" in workload_metadata
    assert "def primary_edge_service_workload()" in workload_metadata
    assert "def internal_service_workloads()" in workload_metadata
    assert "def job_workloads()" in workload_metadata
    assert "def build_image_matrix(" in workload_metadata
    assert "def workload_capability_rows()" in workload_metadata
    assert "def current_runtime_capability_rows()" in workload_metadata
    assert "def edge_symptom_alarm_names(" in platform_inventory
    assert "edge-symptom-alarms <stack-name>" in platform_inventory
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
    workload_metadata = _read("scripts/platform/workload_metadata.py")

    for expected in [
        "python3 -m scripts.platform.workload_metadata image-matrix",
        "APP_PATH",
        "UV_PACKAGE",
        "WORKLOAD_CMD",
    ]:
        assert expected in (
            app_build_workflow if "python3" in expected else workload_metadata
        )


def test_makefile_operator_entrypoints_use_declared_edge_service() -> None:
    makefile = _read("Makefile")

    assert "python3 -m scripts.platform.workload_metadata primary-edge" in makefile
    assert "--service $(PRIMARY_EDGE_SERVICE)" in makefile
    assert 'ECS_SERVICE="$${ECS_SERVICE:-$(PRIMARY_EDGE_SERVICE)}"' in makefile
    assert "SERVICE_NAME           ?= $(PRIMARY_EDGE_SERVICE)" in makefile
    assert 'RELEASE_EVENTS_DIR="$(RELEASE_EVENTS_DIR)"' in makefile
    assert '--service-name "$(SERVICE_NAME)"' in makefile
    assert '--lookback-minutes "$(LOOKBACK_MINUTES)"' in makefile
    assert '--output-dir "$(INCIDENT_EVIDENCE_DIR)"' in makefile
    assert "release-evidence-runs:" in makefile
    assert (
        "RUN_ID\\tWORKFLOW\\tBRANCH\\tSTATUS\\tCONCLUSION\\tCREATED_AT\\tTITLE\\tURL"
        in makefile
    )
    assert "gh run list \\" in makefile
    assert (
        "--json databaseId,workflowName,displayTitle,headBranch,status,conclusion,createdAt,url"
        in makefile
    )
    assert "App Build" in makefile
    assert "App Deploy" in makefile
    assert "Infra Apply" in makefile
    assert "release-evidence-download:" in makefile
    assert "Set GH_RUN_ID=<workflow-run-id>" in makefile
    assert 'gh run download "$(GH_RUN_ID)"' in makefile
    assert "--pattern 'release-evidence-*'" in makefile
    assert "workload-capability-matrix:" in makefile
    assert "python3 -m scripts.platform.workload_metadata capability-matrix" in (
        makefile
    )
    assert "capability-implementation-matrix:" in makefile
    assert "python3 -m scripts.platform.workload_metadata implementation-matrix" in (
        makefile
    )


def test_observability_delivery_inventory_uses_workload_spec() -> None:
    observability_delivery = _read(
        "scripts/observability/verify_observability_delivery.py"
    )
    platform_inventory = _read("scripts/observability/platform_inventory.py")
    workload_metadata = _read("scripts/platform/workload_metadata.py")

    assert (
        "from scripts.platform.workload_metadata import primary_async_eventing_workload"
        in platform_inventory
    )
    assert (
        "from scripts.platform.workload_metadata import scheduled_job_workloads"
        in platform_inventory
    )
    assert "def workload_capabilities(" in workload_metadata
    assert "def primary_async_eventing_workload()" in workload_metadata
    assert "def scheduled_job_workloads()" in workload_metadata
    assert "def workload_log_group_suffixes()" in platform_inventory
    assert "def edge_service_repository() -> str:" in platform_inventory
    assert "def _edge_release_alarm_suffixes()" in platform_inventory
    assert "def _edge_incident_only_alarm_suffixes()" in platform_inventory
    assert 'REQUIRED_SUPPORT_LOG_GROUP_SUFFIXES = ["liquibase", "pgbouncer"]' in (
        platform_inventory
    )
    assert "_WORKLOAD_ALARM_SUFFIXES_BY_NAME" in platform_inventory
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
    workload_metadata = _read("scripts/platform/workload_metadata.py")
    verify_post_deploy = _read("scripts/release/verify_post_deploy.py")

    assert (
        "from scripts.observability.platform_inventory import dapr_workload_service_name"
        in (incident_bundle)
    )
    assert 'ROOT / "platform" / "workloads.json"' in workload_metadata
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
    messaging = _read("infra/app/messaging.tf")
    encryption = _read("infra/app/encryption.tf")

    assert (
        'jsondecode(file("${path.module}/../../platform/workloads.json"))' in inventory
    )
    assert "api_service_port" in inventory
    assert "workload_capabilities = {" in inventory
    assert (
        'workload.kind == "service" && workload.operational.class == "edge-service"'
        in inventory
    )
    assert (
        'workload.kind == "job" && workload.operational.class == "scheduled-job"'
        in inventory
    )
    assert "can(workload.dapr)" in inventory
    assert 'workload.database.pooling == "transaction_pool"' in inventory
    assert 'workload.database.pooling == "direct"' in inventory
    assert "workload.traces.supported" in inventory
    assert "primary_edge_workload_name" in inventory
    assert (
        'capabilities.edge_service && capabilities.edge_exposure == "public"'
        in inventory
    )
    assert (
        "local.workloads_by_name[local.primary_edge_workload_name].service.port"
        in inventory
    )
    assert "primary_async_eventing_workload_name" in inventory
    assert "primary_async_eventing_dapr" in inventory
    assert "primary_async_eventing_repository" in inventory
    assert "primary_async_eventing_service_port" in inventory
    assert "primary_async_eventing_topic_name" in inventory
    assert "primary_async_eventing_pubsub_name" in inventory
    assert "database_runtime_values_by_pooling = {" in inventory
    assert "workload_log_configuration = {" in inventory
    assert "trace_endpoint = (" in inventory
    assert "workload_trace_env_overrides = {" in inventory
    assert "workload_async_eventing_env_defaults = {" in inventory
    assert (
        'OTEL_SERVICE_NAME                  = "${local.name}-${workload.image.repository}"'
        in inventory
    )
    assert 'DAPR_HTTP_PORT     = "3500"' in inventory
    assert 'local.workload_environment["api"]' in compute
    assert 'local.workload_secrets["api"]' in compute
    assert 'resource "aws_ecs_task_definition" "api"' in compute
    assert "api_task_definition_containers = [" in compute
    assert (
        "container_definitions    = jsonencode(local.api_task_definition_containers)"
        in compute
    )
    assert "aws_ecs_task_definition.api" in compute
    assert "depends_on" in compute
    assert "local.workload_environment[each.key]" in jobs
    assert "local.workload_secrets[each.key]" in jobs
    assert 'local.workload_environment["order_event_consumer"]' in jobs
    assert "for name, workload in local.workloads_by_name" in ecr
    assert "containerPort = local.api_service_port" in compute
    assert "container_port   = local.api_service_port" in compute
    assert 'resource "aws_ecs_service" "api"' in compute
    assert "ignore_changes = [task_definition]" in compute
    assert "support_job_workloads = {" in jobs
    assert 'resource "aws_ecs_task_definition" "support_job"' in jobs
    assert "for_each = local.support_job_workloads" in jobs
    assert "module.ecr[each.key]" in jobs
    assert "name = each.value.container_name" in jobs
    assert "logConfiguration = local.workload_log_configuration[each.key]" in (jobs)
    assert 'resource "aws_cloudwatch_log_group" "support_job"' in jobs
    assert 'aws_cloudwatch_log_group.support_job["data_export_job"].name' in jobs
    assert (
        'aws_ecs_task_definition.support_job["data_export_job"].arn_without_revision'
        in jobs
    )
    assert 'resource "aws_ecs_service" "order_event_consumer"' in jobs
    assert "ignore_changes = [task_definition]" in jobs
    assert "support_task_definition_defaults = {" in jobs
    assert "async_eventing_dapr_config_loader_command = join(" in jobs
    assert "async_eventing_dapr_loader_dependency = [" in jobs
    assert "primary_async_eventing_port_mappings = [" in jobs
    assert "primary_async_eventing_health_check = {" in jobs
    assert "primary_async_eventing_daprd_command = [" in jobs
    assert "primary_async_eventing_queue_name" in messaging
    assert "runtime_config_bucket_name" in messaging
    assert "primary_async_eventing_dapr_config_prefix" in messaging
    assert "local.primary_async_eventing_topic_name" in messaging
    assert "local.primary_async_eventing_dapr_config_prefix" in jobs
    assert "local.primary_async_eventing_topic_name" in encryption

    for workload in contract["workloads"]:
        workload_name = workload["name"]
        if workload_name == "order_event_consumer":
            assert "local.primary_async_eventing_workload_name" in inventory
            assert f'local.workload_environment["{workload_name}"]' in jobs
            assert f'local.workload_secrets["{workload_name}"]' in jobs
        elif workload_name in {"backfill_worker", "data_export_job"}:
            assert workload_name in jobs
            assert "local.workload_environment[each.key]" in jobs
            assert "local.workload_secrets[each.key]" in jobs
        else:
            assert f"{workload_name} = " in inventory
            assert f'local.workload_environment["{workload_name}"]' in compute
            assert f'local.workload_secrets["{workload_name}"]' in compute


def test_infra_root_prefers_rebuildability_over_state_migration_baggage() -> None:
    infra_app_tf = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "infra" / "app").glob("*.tf"))
    )

    assert "moved {" not in infra_app_tf
    for removed in [
        "module.ecr_app",
        'module.ecr["app"]',
        'module.ecr["worker"]',
        'module.ecs.module.service["app"]',
    ]:
        assert removed not in infra_app_tf


def test_disposable_runtime_artifacts_destroy_cleanly() -> None:
    ecr_tf = _read("infra/app/ecr.tf")
    edge_access_logs_tf = _read("infra/app/edge_access_logs.tf")
    messaging_tf = _read("infra/app/messaging.tf")

    assert (
        "repository_force_delete = true" in ecr_tf
        or "repository_force_delete         = true" in ecr_tf
    )
    assert "force_destroy = true" in edge_access_logs_tf
    assert "force_destroy = true" in messaging_tf


def test_infra_variable_surface_uses_canonical_runtime_names() -> None:
    variables_tf = _read("infra/app/variables.tf")
    stack_tfvars = _read("infra/app/stack.tfvars")
    compute_tf = _read("infra/app/compute_ecs.tf")
    jobs_tf = _read("infra/app/workload_jobs.tf")

    for expected in [
        'variable "api_cpu"',
        'variable "api_memory"',
        'variable "api_bootstrap_desired_count"',
        'variable "backfill_worker_cpu"',
        'variable "backfill_worker_memory"',
        'variable "order_event_consumer_bootstrap_desired_count"',
        'variable "enable_api_symptom_cloudwatch_alarms"',
        'variable "bootstrap_image_tag"',
        'variable "api_image_tag"',
    ]:
        assert expected in variables_tf

    for removed in [
        'variable "app_cpu"',
        'variable "app_memory"',
        'variable "app_desired_count"',
        'variable "api_desired_count"',
        'variable "worker_cpu"',
        'variable "worker_memory"',
        'variable "order_event_consumer_desired_count"',
        'variable "enable_app_symptom_cloudwatch_alarms"',
        'variable "initial_image_tag"',
        'variable "app_image_tag"',
    ]:
        assert removed not in variables_tf

    assert "bootstrap_image_tag" in stack_tfvars
    assert "api_image_tag" in stack_tfvars
    assert "initial_image_tag" not in stack_tfvars
    assert "app_image_tag" not in stack_tfvars
    assert "var.api_cpu" in compute_tf
    assert "var.api_memory" in compute_tf
    assert "var.api_bootstrap_desired_count" in compute_tf
    assert "var.enable_api_symptom_cloudwatch_alarms" in compute_tf
    assert "var.api_image_tag" in compute_tf
    assert "var.bootstrap_image_tag" in compute_tf
    assert "var.backfill_worker_cpu" in jobs_tf
    assert "var.backfill_worker_memory" in jobs_tf
    assert "var.order_event_consumer_bootstrap_desired_count" in jobs_tf
    assert "var.bootstrap_image_tag" in jobs_tf


def test_app_deploy_owns_service_activation_after_bootstrap() -> None:
    workflow = _read(".github/workflows/app-deploy.yml")
    deploy_script = _read("scripts/ci/ci_deploy_ecs_service.sh")
    variables_tf = _read("infra/app/variables.tf")

    assert 'variable "api_bootstrap_desired_count"' in variables_tf
    assert "default     = 0" in variables_tf
    assert 'variable "order_event_consumer_bootstrap_desired_count"' in variables_tf
    assert (
        'scripts/ci/ci_deploy_ecs_service.sh "${STACK_NAME}" "${{ steps.primary-service.outputs.service }}" /tmp/api-task-definition.json 1'
        in workflow
    )
    assert (
        'scripts/ci/ci_deploy_ecs_service.sh "${STACK_NAME}" "$service" "$task_definition" 1'
        in workflow
    )
    assert "[desired-count]" in deploy_script
    assert 'update_args+=(--desired-count "$DESIRED_COUNT")' in deploy_script


def test_compose_build_args_and_ports_align_with_workload_spec() -> None:
    contract = json.loads(_read("platform/workloads.json"))
    compose = yaml.safe_load(_read("compose.yaml"))
    services = compose["services"]

    for workload in contract["workloads"]:
        compose_name = _compose_service_name(workload)
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

    order_event_workload = _workload_by_name(contract, "order_event_consumer")
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
    shared_config_text = (ROOT / "packages" / "infrastructure" / "config.py").read_text(
        encoding="utf-8"
    )
    shared_names = set(ENV_NAME_PATTERN.findall(shared_config_text))

    for workload in contract["workloads"]:
        config_text = _config_path(workload).read_text(encoding="utf-8")
        discovered_names = set(ENV_NAME_PATTERN.findall(config_text))
        if "PostgresRuntimeSettings" in config_text:
            discovered_names |= shared_names
        assert _declared_config_names(workload) == discovered_names


def test_outputs_use_canonical_workload_and_runtime_names() -> None:
    outputs = _read("infra/app/outputs.tf")

    for expected in [
        'output "api_fqdn"',
        'output "api_unhealthy_targets_alarm_name"',
        'output "api_symptom_cloudwatch_alarms_enabled"',
        'output "api_target_5xx_alarm_name"',
        'output "api_target_latency_alarm_name"',
        'output "order_event_consumer_service_name"',
        'output "data_export_schedule_name"',
        'output "data_export_scheduler_target_errors_alarm_name"',
        'output "data_export_success_cloudwatch_alarm_enabled"',
        'output "data_export_success_missing_alarm_name"',
        'output "rds_endpoint"',
        'output "rds_instance_identifier"',
        'output "db_secret_arn"',
        'output "rds_cpu_high_alarm_name"',
        'output "rds_free_storage_low_alarm_name"',
        'output "rds_connections_high_alarm_name"',
        'output "data_hub_bucket_name"',
        'output "ecs_cluster_name"',
        'output "api_service_name"',
        'output "order_events_queue_url"',
        'output "order_events_dlq_name"',
        'output "order_events_dlq_visible_alarm_name"',
    ]:
        assert expected in outputs

    for removed in [
        'output "alb_dns_name"',
        'output "alb_url"',
        'output "acm_certificate_arn"',
        'output "edge_waf_web_acl_arn"',
        'output "ecr_api_repository_url"',
        'output "ecr_backfill_worker_repository_url"',
        'output "ecr_liquibase_repository_url"',
        'output "ecr_data_export_job_repository_url"',
        'output "ecr_order_event_consumer_repository_url"',
        'output "backfill_worker_task_definition_arn"',
        'output "data_export_job_task_definition_arn"',
        'output "data_export_success_metric_namespace"',
        'output "data_export_success_metric_name"',
        'output "liquibase_task_definition_arn"',
        'output "data_hub_prefixes"',
        'output "runtime_task_exec_role_arn"',
        'output "api_task_role_arn"',
        'output "order_events_topic_arn"',
        'output "private_subnet_ids"',
        'output "runtime_security_group_id"',
        'output "github_actions_role_arn"',
        'output "alb_access_logs_bucket_name"',
        'output "adot_sidecar_enabled"',
        'output "app_unhealthy_targets_alarm_name"',
        'output "app_symptom_cloudwatch_alarms_enabled"',
        'output "app_target_5xx_alarm_name"',
        'output "app_target_latency_alarm_name"',
        'output "ecr_app_repository_url"',
        'output "ecr_worker_repository_url"',
        'output "worker_task_definition_arn"',
        'output "app_service_name"',
        'output "app_task_exec_role_arn"',
        'output "app_task_role_arn"',
        'output "app_security_group_id"',
    ]:
        assert removed not in outputs


def test_operator_surface_prefers_canonical_api_service_output() -> None:
    operator_surface = _operator_surface_text()

    assert "output -raw api_service_name" in operator_surface
    assert "output -raw app_service_name" not in operator_surface


def test_alarm_surface_prefers_canonical_api_alarm_outputs() -> None:
    alarm_surface = _alarm_surface_text()

    assert "output -raw api_unhealthy_targets_alarm_name" in alarm_surface
    assert "output -raw api_target_5xx_alarm_name" in alarm_surface
    assert "output -raw api_target_latency_alarm_name" in alarm_surface
    assert "output -raw app_unhealthy_targets_alarm_name" not in alarm_surface
    assert "output -raw app_target_5xx_alarm_name" not in alarm_surface
    assert "output -raw app_target_latency_alarm_name" not in alarm_surface


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

    for workload in contract["workloads"]:
        compose_name = _compose_service_name(workload)
        compose_env = set(services[compose_name].get("environment", {}).keys())
        declared_names = set(workload["config"]["env"]) | set(
            workload["config"]["secrets"]
        )
        assert compose_env.issubset(declared_names)


def test_compose_database_wiring_matches_declared_pooling_model() -> None:
    contract = json.loads(_read("platform/workloads.json"))
    compose = yaml.safe_load(_read("compose.yaml"))
    services = compose["services"]

    for workload in contract["workloads"]:
        compose_name = _compose_service_name(workload)
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
    conformance = _runtime_conformance()

    for workload in contract["workloads"]:
        workload_conformance = _workload_conformance(workload, conformance)
        conformance_names = set(workload_conformance["env"]) | set(
            workload_conformance["secrets"]
        )
        assert conformance_names.issubset(_declared_config_names(workload))


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
