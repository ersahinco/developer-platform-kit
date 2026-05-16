from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import scripts.observability.verify_observability_delivery as delivery  # noqa: E402


EXPECTED_LOG_GROUP_SUFFIXES = set(delivery.EXPECTED_LOG_GROUP_SUFFIXES)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _resource_block(terraform: str, resource_type: str, name: str) -> str:
    start = terraform.index(f'resource "{resource_type}" "{name}"')
    next_resource = terraform.find('\nresource "', start + 1)
    if next_resource == -1:
        return terraform[start:]
    return terraform[start:next_resource]


def test_cloud_observability_is_adot_sidecar_not_hosted_lgtm() -> None:
    observability_tf = _read("infra/app/observability.tf")
    compute_tf = _read("infra/app/compute_ecs.tf")
    variables_tf = _read("infra/app/variables.tf")
    workflows = "\n".join(
        [
            _read(".github/workflows/app-build.yml"),
            _read(".github/workflows/app-deploy.yml"),
            _read(".github/workflows/app-rollback-drill.yml"),
        ]
    )
    infra = "\n".join(
        [
            observability_tf,
            compute_tf,
            _read("infra/app/workload_jobs.tf"),
            _read("infra/app/runtime_identity.tf"),
            _read("infra/app/outputs.tf"),
        ]
    )

    assert "enable_adot_sidecar" in variables_tf
    assert "aws-otel-collector:v0.47.0" in variables_tf
    assert "adot_collector_container" in observability_tf
    assert 'command   = ["--config=env:ADOT_COLLECTOR_CONFIG"]' in (observability_tf)
    assert "http://127.0.0.1:4318/v1/traces" in compute_tf
    assert "default_adot_collector_config" in observability_tf
    assert "job_name: app" in observability_tf

    for retired in [
        'resource "aws_ecs_service" "grafana"',
        'resource "aws_ecs_service" "loki"',
        'resource "aws_ecs_service" "prometheus"',
        'resource "aws_ecs_service" "tempo"',
        "awsfirelens",
        "log-router",
        'module "ecr_firelens"',
        "enable_observability_stack",
        "firelens",
    ]:
        assert retired not in infra.lower()
        assert retired not in workflows.lower()


def test_local_grafana_stack_uses_prometheus_loki_tempo_without_cloudwatch() -> None:
    datasources = _read(
        "observability/grafana/provisioning/datasources/datasources.yml"
    )

    assert "type: prometheus" in datasources
    assert "type: loki" in datasources
    assert "type: tempo" in datasources
    assert "cloudwatch" not in datasources.lower()


def test_terraform_declares_only_expected_cloud_log_groups() -> None:
    infra = "\n".join(
        [
            _read("infra/app/app_log_groups.tf"),
            _read("infra/app/observability.tf"),
            _read("infra/app/workload_jobs.tf"),
            _read("infra/app/compute_ecs.tf"),
        ]
    )
    declared_names = set(re.findall(r'"/ecs/\$\{local\.name\}/([^"]+)"', infra))

    assert declared_names == EXPECTED_LOG_GROUP_SUFFIXES


def test_alb_access_logs_are_not_coupled_to_observability_stack() -> None:
    edge_tf = _read("infra/app/edge.tf")
    edge_logs_tf = _read("infra/app/edge_access_logs.tf")
    outputs_tf = _read("infra/app/outputs.tf")

    assert "local.alb_access_logs_bucket_name" in edge_tf
    assert "aws_s3_bucket_policy.alb_access_logs" in edge_tf
    assert 'resource "aws_s3_bucket" "alb_access_logs"' in edge_logs_tf
    assert "alb_access_logs_bucket_name" in outputs_tf
    assert "observability_bucket_name" not in edge_tf


def test_app_service_uses_ecs_native_rollback_detection() -> None:
    compute_tf = _read("infra/app/compute_ecs.tf")
    app_task_identity_tf = _read("infra/app/app_task_identity.tf")
    app_log_groups_tf = _read("infra/app/app_log_groups.tf")
    workload_jobs_tf = _read("infra/app/workload_jobs.tf")
    outputs_tf = _read("infra/app/outputs.tf")

    app_service_start = compute_tf.index("services = {")
    app_container_start = compute_tf.index("container_definitions =", app_service_start)
    app_service_config = compute_tf[app_service_start:app_container_start]

    assert "deployment_circuit_breaker" in app_service_config
    assert "enable   = true" in app_service_config
    assert "rollback = true" in app_service_config
    assert 'strategy             = "ROLLING"' in app_service_config
    assert 'bake_time_in_minutes = "5"' in app_service_config
    assert "create_infrastructure_iam_role = false" in app_service_config
    assert "alarms = var.enable_app_symptom_cloudwatch_alarms" in app_service_config
    assert "create_task_definition = false" in app_service_config
    assert "task_definition_arn    = data.aws_ecs_task_definition.app_current.arn" in (
        app_service_config
    )
    assert "create_tasks_iam_role  = false" in app_service_config
    assert "tasks_iam_role_arn     = aws_iam_role.app_task.arn" in app_service_config
    assert 'from = module.ecs.module.service["app"].aws_iam_role.tasks[0]' in (
        app_task_identity_tf
    )
    assert 'resource "aws_cloudwatch_log_group" "app"' in app_log_groups_tf
    assert 'resource "aws_cloudwatch_log_group" "pgbouncer"' in app_log_groups_tf
    assert "task_role_arn            = aws_iam_role.app_task.arn" in workload_jobs_tf
    assert "value       = aws_iam_role.app_task.arn" in outputs_tf


def test_every_long_running_ecs_service_has_circuit_breaker_rollback() -> None:
    workload_jobs_tf = _read("infra/app/workload_jobs.tf")
    order_event_consumer = _resource_block(
        workload_jobs_tf, "aws_ecs_service", "order_event_consumer"
    )

    assert "deployment_circuit_breaker" in order_event_consumer
    assert "enable   = true" in order_event_consumer
    assert "rollback = true" in order_event_consumer


def test_log_groups_dashboard_is_loki_only_and_matches_cloud_groups() -> None:
    dashboard = json.loads(_read("observability/grafana/dashboards/log-groups.json"))

    assert dashboard["title"] == "Log Groups"
    assert dashboard["uid"] == "aws-sdlc-log-groups"

    def walk(value: object) -> list[str]:
        if isinstance(value, dict):
            found = []
            if value.get("type") in {"loki", "prometheus", "tempo", "cloudwatch"}:
                found.append(str(value["type"]))
            for nested in value.values():
                found.extend(walk(nested))
            return found
        if isinstance(value, list):
            found = []
            for nested in value:
                found.extend(walk(nested))
            return found
        return []

    datasource_types = walk(dashboard)
    assert datasource_types
    assert set(datasource_types) == {"loki"}
    assert "log_group" in json.dumps(dashboard)
    assert "Open Selected Group In Explore" in json.dumps(dashboard)

    variables = {item["name"]: item for item in dashboard["templating"]["list"]}
    log_group_variable = variables["log_group"]
    container_variable = variables["container"]

    for suffix in EXPECTED_LOG_GROUP_SUFFIXES:
        assert f"/ecs/aws-sdlc-containers/{suffix}" in log_group_variable["query"]
        assert suffix in container_variable["query"]


def test_local_prometheus_scrapes_app_and_stack_metrics() -> None:
    local_prometheus = _read("observability/prometheus/prometheus.yml")

    assert "job_name: app" in local_prometheus
    assert "metrics_path: /metrics" in local_prometheus
    assert "job_name: prometheus" in local_prometheus
    assert "job_name: loki" in local_prometheus
    assert "job_name: tempo" in local_prometheus
