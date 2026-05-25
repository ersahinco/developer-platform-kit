from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

PLATFORM_RUNTIME_SURFACES = [
    "infra/app/app_task_identity.tf",
    "infra/app/app_log_groups.tf",
    "infra/app/compute_ecs.tf",
    "infra/app/edge.tf",
    "infra/app/outputs.tf",
    "scripts/ci/ci_resolve_ecs_network.sh",
    ".github/workflows/app-deploy.yml",
]

FORBIDDEN_INTERNAL_LABELS = [
    "api_task_assume",
    'resource "aws_iam_role" "api_task"',
    'resource "aws_iam_policy" "api_task"',
    'resource "aws_iam_role_policy_attachment" "api_task_internal"',
    "api_task_container_definitions",
    "api_task_definition_containers",
    'resource "aws_ecs_task_definition" "api"',
    'data "aws_ecs_task_definition" "api_current"',
    'resource "aws_ecs_service" "api"',
    'resource "aws_cloudwatch_log_group" "api"',
    'resource "aws_security_group" "api"',
    'resource "aws_lb_target_group" "api"',
    'resource "aws_cloudwatch_metric_alarm" "api_unhealthy_targets"',
    'resource "aws_cloudwatch_metric_alarm" "api_target_5xx"',
    'resource "aws_cloudwatch_metric_alarm" "api_target_latency"',
    'resource "aws_acm_certificate" "api"',
    'resource "aws_route53_record" "api_cert_validation"',
    'resource "aws_acm_certificate_validation" "api"',
    'resource "aws_route53_record" "api_alias"',
    "/tmp/api-task-definition.json",
    "${STACK_NAME}-api-*",
    "Failed to resolve api security group",
]


def test_primary_edge_platform_runtime_surfaces_do_not_use_api_internal_labels() -> (
    None
):
    runtime_surface_text = "\n".join(
        (ROOT / path).read_text(encoding="utf-8") for path in PLATFORM_RUNTIME_SURFACES
    )

    for forbidden in FORBIDDEN_INTERNAL_LABELS:
        assert forbidden not in runtime_surface_text


def test_primary_edge_runtime_identity_uses_deterministic_repo_owned_names() -> None:
    task_identity = (ROOT / "infra/app/app_task_identity.tf").read_text(
        encoding="utf-8"
    )
    renderer = (ROOT / "scripts/ci/render_ecs_task_definition.py").read_text(
        encoding="utf-8"
    )

    assert 'resource "aws_iam_role" "primary_edge_task_deploy"' in task_identity
    assert 'name        = "${local.name}-primary-edge-task"' in task_identity
    assert 'resource "aws_iam_policy" "primary_edge_task_deploy"' in task_identity
    assert 'name        = "${local.name}-primary-edge-task-policy"' in task_identity
    assert 'resource "aws_iam_role" "primary_edge_task"' not in task_identity
    assert 'name_prefix = "primary-edge-tasks-"' not in task_identity
    assert "describe-task-definition" not in renderer
    assert "_primary_edge_task_role_name" in renderer
