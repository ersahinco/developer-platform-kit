from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import scripts.observability.verify_observability_delivery as delivery  # noqa: E402


EXPECTED_LOG_GROUP_SUFFIXES = set(delivery.EXPECTED_LOG_GROUP_SUFFIXES)
EXPECTED_LOKI_LOG_GROUP_SUFFIXES = set(delivery.EXPECTED_LOKI_LOG_GROUP_SUFFIXES)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_firelens_dual_writes_every_expected_workload_log_to_cloudwatch_and_loki() -> (
    None
):
    config = _read("observability/firelens/fluent-bit.conf")

    for suffix in EXPECTED_LOKI_LOG_GROUP_SUFFIXES:
        match = f"{suffix}-firelens*"
        assert f"Name cloudwatch_logs\n    Match {match}" in config
        assert f"log_group_name /ecs/${{STACK_NAME}}/{suffix}" in config
        assert f"Name loki\n    Match {match}" in config
        assert f"service={suffix}" in config
        assert f"log_group=/ecs/${{STACK_NAME}}/{suffix}" in config


def test_local_promtail_assigns_cloudwatch_like_log_group_labels() -> None:
    config = _read("observability/promtail/promtail.yml")

    assert "target_label: log_group" in config
    assert 'replacement: "/ecs/aws-sdlc-containers/$1"' in config


def test_terraform_declares_only_the_expected_stack_log_groups() -> None:
    infra = "\n".join(
        [
            _read("infra/app/observability.tf"),
            _read("infra/app/workload_jobs.tf"),
            _read("infra/app/compute_ecs.tf"),
        ]
    )
    declared_names = set(re.findall(r'"/ecs/\$\{local\.name\}/([^"]+)"', infra))

    assert declared_names == EXPECTED_LOG_GROUP_SUFFIXES


def test_grafana_stack_uses_prometheus_loki_tempo_without_cloudwatch_or_xray() -> None:
    datasources = _read(
        "observability/grafana/provisioning/datasources/datasources.yml"
    )
    observability_tf = _read("infra/app/observability.tf")
    compute_tf = _read("infra/app/compute_ecs.tf")
    telemetry_py = _read("apps/api/src/aws_sdlc_api/telemetry.py")

    assert "type: prometheus" in datasources
    assert "type: loki" in datasources
    assert "type: tempo" in datasources
    assert "cloudwatch" not in datasources.lower()

    assert "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT" in compute_tf
    assert "tempo.${local.observability_dns_namespace}:4318/v1/traces" in compute_tf
    combined = f"{observability_tf}\n{compute_tf}\n{telemetry_py}"
    assert "xray" not in combined.lower()


def test_log_groups_dashboard_is_provisioned_and_uses_loki_only() -> None:
    dashboard = json.loads(_read("observability/grafana/dashboards/log-groups.json"))
    observability_tf = _read("infra/app/observability.tf")

    assert dashboard["title"] == "Log Groups"
    assert dashboard["uid"] == "aws-sdlc-log-groups"
    assert "log-groups.json" in observability_tf
    assert "grafana_log_groups_dashboard" in observability_tf

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
    logs_expr = dashboard["panels"][1]["targets"][0]["expr"]
    assert 'log_group=~"$log_group"' in logs_expr
    assert 'container=~"$container"' in logs_expr

    variables = {item["name"]: item for item in dashboard["templating"]["list"]}
    log_group_variable = variables["log_group"]
    container_variable = variables["container"]
    assert log_group_variable["type"] == "custom"
    assert container_variable["type"] == "custom"

    for suffix in EXPECTED_LOKI_LOG_GROUP_SUFFIXES:
        assert f"/ecs/aws-sdlc-containers/{suffix}" in log_group_variable["query"]
        assert suffix in container_variable["query"]


def test_loki_tunnel_has_ecs_exec_support() -> None:
    makefile = _read("Makefile")
    tunnel_script = _read("scripts/operator/loki_tunnel.sh")
    observability_tf = _read("infra/app/observability.tf")

    assert "loki-tunnel" in makefile
    assert "observability-stack-deploy" in makefile
    assert "observability_loki_service_name" in tunnel_script
    assert 'aws_iam_role_policy" "loki_ssm_exec' in observability_tf
    loki_service_start = observability_tf.index('resource "aws_ecs_service" "loki"')
    prometheus_service_start = observability_tf.index(
        'resource "aws_ecs_task_definition" "prometheus"'
    )
    loki_service = observability_tf[loki_service_start:prometheus_service_start]
    assert "enable_execute_command = true" in loki_service
    assert "aws_iam_role_policy.loki_ssm_exec" in loki_service


def test_firelens_rollout_helpers_cover_firelens_using_task_families() -> None:
    makefile = _read("Makefile")
    build_script = _read("scripts/release/build_push_firelens.py")
    roll_script = _read("scripts/release/roll_firelens_image.py")

    assert "firelens-build-push" in makefile
    assert "firelens-roll" in makefile
    assert "observability/firelens/Dockerfile" in build_script
    assert "--platform" in build_script
    assert "linux/amd64" in build_script

    for family in [
        "aws-sdlc-containers",
        "aws-sdlc-containers-order-event-consumer",
        "aws-sdlc-containers-grafana",
        "aws-sdlc-containers-loki",
        "aws-sdlc-containers-prometheus",
        "aws-sdlc-containers-tempo",
        "aws-sdlc-containers-worker",
        "aws-sdlc-containers-data-export-job",
        "aws-sdlc-containers-liquibase",
    ]:
        assert family in roll_script

    assert "log-router" in roll_script
    assert "register-task-definition" in roll_script
    assert "update-service" in roll_script
    assert "services-stable" in roll_script


def test_app_rollout_helpers_support_observability_cloud_traffic_fixture() -> None:
    makefile = _read("Makefile")
    build_script = _read("scripts/release/build_push_app.py")
    roll_script = _read("scripts/release/roll_app_image.py")

    assert "app-build-push" in makefile
    assert "app-roll" in makefile
    assert "apps/api/Dockerfile" in build_script
    assert "--platform" in build_script
    assert "linux/amd64" in build_script
    assert "APP_IMAGE_TAG" in roll_script
    assert "aws-sdlc-containers" in roll_script
    assert "register-task-definition" in roll_script
    assert "update-service" in roll_script
    assert "services-stable" in roll_script


def test_observability_cloud_traffic_runs_quiet_cloud_log_probes() -> None:
    makefile = _read("Makefile")
    probe_script = _read("scripts/observability/run_observability_cloud_jobs.py")

    assert "scripts/observability/generate_cloud_traffic.py" in makefile
    assert "scripts/observability/run_observability_cloud_jobs.py" in makefile
    assert "observability-cloud-jobs" in makefile

    for target in ["worker", "data-export-job", "liquibase", "prometheus", "tempo"]:
        assert target in probe_script

    assert "BACKFILL_MAX_BATCHES" in probe_script
    assert "DATA_EXPORT_RUN_ID" in probe_script
    assert "status" in probe_script
    assert "force-new-deployment" in probe_script


def test_infra_apply_downloads_plan_artifact_into_infra_tree() -> None:
    workflow = _read(".github/workflows/infra-apply.yml")

    assert "actions/download-artifact@v8" in workflow
    assert "path: infra" in workflow
    assert "terraform apply -auto-approve platform.tfplan" in workflow
    assert "working-directory: infra/platform" in workflow
    assert "terraform apply -auto-approve app.tfplan" in workflow
    assert "working-directory: infra/app" in workflow


def test_app_overview_uses_loki_for_order_event_worker_outcomes() -> None:
    dashboard = json.loads(_read("observability/grafana/dashboards/app-overview.json"))
    order_panel = next(
        panel
        for panel in dashboard["panels"]
        if panel["title"] == "Order Event Worker Outcomes"
    )

    assert order_panel["datasource"]["type"] == "loki"
    target = order_panel["targets"][0]
    assert target["datasource"]["type"] == "loki"
    assert "order-event-consumer" in target["expr"]
    assert "outbox_relay" in target["expr"]
    assert "order_event_consumed" in target["expr"]


def test_prometheus_scrapes_app_metrics_and_observability_stack_metrics() -> None:
    local_prometheus = _read("observability/prometheus/prometheus.yml")
    aws_prometheus = _read("infra/app/templates/observability/prometheus.yml.tftpl")

    for config in [local_prometheus, aws_prometheus]:
        assert "job_name: app" in config
        assert "metrics_path: /metrics" in config
        assert "job_name: prometheus" in config
        assert "job_name: loki" in config
        assert "job_name: tempo" in config


def test_observability_docs_list_cloudwatch_log_and_metric_contracts() -> None:
    docs = _read("docs/observability.md")

    for suffix in EXPECTED_LOG_GROUP_SUFFIXES:
        assert f"/ecs/aws-sdlc-containers/{suffix}" in docs

    for metric in [
        "UnHealthyHostCount",
        "HTTPCode_Target_5XX_Count",
        "TargetResponseTime",
        "CPUUtilization",
        "FreeStorageSpace",
        "DatabaseConnections",
        "ApproximateNumberOfMessagesVisible",
        "TargetErrorCount",
        "SuccessCount",
        "ECS/ContainerInsights",
    ]:
        assert metric in docs
