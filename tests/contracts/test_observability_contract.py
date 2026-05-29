from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_cloud_observability_is_adot_sidecar_not_hosted_lgtm() -> None:
    observability_tf = _read("infra/app/observability.tf")
    app_log_groups_tf = _read("infra/app/app_log_groups.tf")
    compute_tf = _read("infra/app/compute_ecs.tf")
    workload_inventory_tf = _read("infra/app/workload_inventory.tf")
    variables_tf = _read("infra/app/variables.tf")
    workflows = "\n".join(
        [
            _read(".github/workflows/app-build.yml"),
            _read(".github/workflows/app-deploy.yml"),
        ]
    )
    infra = "\n".join(
        [
            observability_tf,
            compute_tf,
            workload_inventory_tf,
            _read("infra/app/workload_jobs.tf"),
            _read("infra/app/runtime_identity.tf"),
            _read("infra/app/outputs.tf"),
        ]
    )

    assert "enable_adot_sidecar" in variables_tf
    assert "aws-otel-collector:v0.47.0" in variables_tf
    assert "adot_collector_container" in observability_tf
    assert re.search(
        r'command\s*=\s*\["--config=env:ADOT_COLLECTOR_CONFIG"\]',
        observability_tf,
    )
    assert "http://127.0.0.1:4318/v1/traces" in workload_inventory_tf
    assert "local.workload_environment[local.primary_edge_workload_name]" in compute_tf
    assert "default_adot_collector_config" in observability_tf
    assert "job_name: ${local.primary_edge_repository}" in observability_tf
    assert 'resource "aws_cloudwatch_log_group" "adot"' in app_log_groups_tf
    assert 'name              = "/ecs/${local.name}/adot"' in app_log_groups_tf

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
        "platform/concerns/observability/grafana/provisioning/datasources/"
        "datasources.yml"
    )

    assert "type: prometheus" in datasources
    assert "type: loki" in datasources
    assert "type: tempo" in datasources
    assert "cloudwatch" not in datasources.lower()


def test_alb_access_logs_are_not_coupled_to_observability_stack() -> None:
    edge_tf = _read("infra/app/edge.tf")
    edge_logs_tf = _read("infra/app/edge_access_logs.tf")

    assert "local.alb_access_logs_bucket_name" in edge_tf
    assert "aws_s3_bucket_policy.alb_access_logs" in edge_tf
    assert re.search(r'resource\s+"aws_s3_bucket"\s+"alb_access_logs"', edge_logs_tf)
    assert "observability_bucket_name" not in edge_tf


def test_data_export_success_metric_filter_matches_job_log_shape() -> None:
    workload_jobs_tf = _read("infra/app/workload_jobs.tf")

    assert "$.event" in workload_jobs_tf
    assert "data_export_succeeded" in workload_jobs_tf
    assert "$.status" in workload_jobs_tf
    assert "succeeded" in workload_jobs_tf
    assert "$.log" not in workload_jobs_tf
