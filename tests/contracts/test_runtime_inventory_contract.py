from __future__ import annotations

from ._helpers import load_json, read_text


def test_platform_root_stays_bootstrap_only() -> None:
    platform_tf = "\n".join(
        [
            read_text("infra/platform/github_actions.tf"),
            read_text("infra/platform/network.tf"),
            read_text("infra/platform/outputs.tf"),
            read_text("infra/platform/providers.tf"),
            read_text("infra/platform/variables.tf"),
            read_text("infra/platform/versions.tf"),
        ]
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


def test_app_root_consumes_platform_through_remote_state_outputs() -> None:
    providers_tf = read_text("infra/app/providers.tf")
    app_tf = "\n".join(
        [
            read_text("infra/app/compute_ecs.tf"),
            read_text("infra/app/database.tf"),
            read_text("infra/app/edge.tf"),
            read_text("infra/app/encryption.tf"),
            read_text("infra/app/messaging.tf"),
            read_text("infra/app/object_storage.tf"),
            read_text("infra/app/observability.tf"),
            read_text("infra/app/runtime_identity.tf"),
            read_text("infra/app/workload_inventory.tf"),
            read_text("infra/app/workload_jobs.tf"),
        ]
    )

    assert 'data "terraform_remote_state" "platform"' in providers_tf
    assert "platform = data.terraform_remote_state.platform.outputs" in providers_tf
    assert 'source  = "../platform"' not in app_tf
    assert "data.aws_vpc" not in app_tf
    assert "data.aws_subnets" not in app_tf


def test_terraform_state_uses_s3_lockfiles_only() -> None:
    versions_text = "\n".join(
        [
            read_text("infra/platform/versions.tf"),
            read_text("infra/app/versions.tf"),
        ]
    )

    assert versions_text.count("use_lockfile = true") == 2
    assert "dynamodb_table" not in versions_text


def test_runtime_inventory_loads_workload_contract() -> None:
    contract = load_json("platform/workloads.json")
    inventory = read_text("infra/app/workload_inventory.tf")
    compute = read_text("infra/app/compute_ecs.tf")
    jobs = read_text("infra/app/workload_jobs.tf")
    ecr = read_text("infra/app/ecr.tf")

    assert (
        'jsondecode(file("${path.module}/../../platform/workloads.json"))' in inventory
    )
    assert "workload_capabilities = {" in inventory
    assert "database_runtime_values_by_pooling = {" in inventory
    assert "workload_log_configuration = {" in inventory
    assert "trace_endpoint = (" in inventory
    assert 'local.workload_environment["api"]' in compute
    assert 'local.workload_secrets["api"]' in compute
    assert "local.workload_environment[each.key]" in jobs
    assert "local.workload_secrets[each.key]" in jobs
    assert "for name, workload in local.workloads_by_name" in ecr

    for workload in contract["workloads"]:
        workload_name = workload["name"]
        if workload_name == "api":
            assert f'local.workload_environment["{workload_name}"]' in compute
            assert f'local.workload_secrets["{workload_name}"]' in compute
        elif workload_name == "order_event_consumer":
            assert f'local.workload_environment["{workload_name}"]' in jobs
            assert f'local.workload_secrets["{workload_name}"]' in jobs
        else:
            assert workload_name in jobs


def test_runtime_inventory_preserves_task_definition_drift_boundary() -> None:
    workflow_text = read_text(".github/workflows/infra-apply.yml")
    guard_script = read_text("scripts/ci/ci_guard_infra_plan_blast_radius.sh")
    compute = read_text("infra/app/compute_ecs.tf")
    jobs = read_text("infra/app/workload_jobs.tf")

    assert "allow_ecs_task_definition_changes" in workflow_text
    assert "Guard reviewed plan blast radius" in workflow_text
    assert "aws_ecs_task_definition" in guard_script
    assert "app deploy ownership boundary" in guard_script
    assert "ignore_changes = [task_definition]" in compute
    assert "ignore_changes = [task_definition]" in jobs
