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


def _resource_block(terraform: str, resource_type: str, name: str) -> str:
    start = terraform.index(f'resource "{resource_type}" "{name}"')
    next_resource = terraform.find('\nresource "', start + 1)
    if next_resource == -1:
        return terraform[start:]
    return terraform[start:next_resource]


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
            _read("infra/app/app_log_groups.tf"),
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
    telemetry_py = _read("apps/api/telemetry.py")

    assert "type: prometheus" in datasources
    assert "type: loki" in datasources
    assert "type: tempo" in datasources
    assert "cloudwatch" not in datasources.lower()

    assert "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT" in compute_tf
    assert "tempo.${local.observability_dns_namespace}:4318/v1/traces" in compute_tf
    combined = f"{observability_tf}\n{compute_tf}\n{telemetry_py}"
    assert "xray" not in combined.lower()


def test_portable_incident_evidence_is_assistant_ready_without_cloud_dependency() -> (
    None
):
    observability_doc = _read("docs/observability.md")
    makefile = _read("Makefile")
    evidence_script = _read("scripts/observability/incident_evidence_bundle.py")
    firelens_config = _read("observability/firelens/fluent-bit.conf")
    promtail_config = _read("observability/promtail/promtail.yml")

    assert "make incident-evidence" in observability_doc
    assert "OSS-portable" in observability_doc
    assert "Grafana Cloud AI" in observability_doc
    assert "incident-evidence" in makefile
    assert "incident_evidence_bundle.py" in makefile

    for field in [
        "stack",
        "environment",
        "service",
        "container",
        "request_id",
        "trace_id",
        "task_definition",
        "image_tag",
        "github_run_id",
        "order_id",
        "event_id",
        "export_run_id",
    ]:
        assert f'"{field}"' in evidence_script

    assert "query_hints" in evidence_script
    assert "AWS SDLC Containers / App Overview" in evidence_script
    assert "AWS SDLC Containers / Log Groups" in evidence_script
    assert (
        "cloudwatch"
        not in _read(
            "observability/grafana/provisioning/datasources/datasources.yml"
        ).lower()
    )

    for label in ["stack=", "environment=", "service=", "container=", "log_group="]:
        assert label in firelens_config
    for label in [
        "target_label: stack",
        "target_label: environment",
        "target_label: service",
        "target_label: container",
        "target_label: log_group",
    ]:
        assert label in promtail_config


def test_app_service_uses_ecs_native_rollback_detection() -> None:
    compute_tf = _read("infra/app/compute_ecs.tf")
    app_task_identity_tf = _read("infra/app/app_task_identity.tf")
    app_log_groups_tf = _read("infra/app/app_log_groups.tf")
    runtime_identity_tf = _read("infra/app/runtime_identity.tf")
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
    assert "aws_cloudwatch_metric_alarm.app_target_5xx[0].alarm_name" in (
        app_service_config
    )
    assert "aws_cloudwatch_metric_alarm.app_target_latency[0].alarm_name" in (
        app_service_config
    )
    assert "create_task_definition = false" in app_service_config
    assert "task_definition_arn    = data.aws_ecs_task_definition.app_current.arn" in (
        app_service_config
    )
    assert "create_tasks_iam_role  = false" in app_service_config
    assert "tasks_iam_role_arn     = aws_iam_role.app_task.arn" in app_service_config
    assert 'from = module.ecs.module.service["app"].aws_iam_role.tasks[0]' in (
        app_task_identity_tf
    )
    assert (
        'from = module.ecs.module.service["app"].module.container_definition["app"].aws_cloudwatch_log_group.this[0]'
        in app_log_groups_tf
    )
    assert 'resource "aws_cloudwatch_log_group" "app"' in app_log_groups_tf
    assert 'resource "aws_cloudwatch_log_group" "pgbouncer"' in app_log_groups_tf
    assert "role       = aws_iam_role.app_task.name" in runtime_identity_tf
    assert "task_role_arn            = aws_iam_role.app_task.arn" in workload_jobs_tf
    assert "value       = aws_iam_role.app_task.arn" in outputs_tf
    assert 'name = "ROLLOUT_DRILL_FAULT_MODE", value = "off"' in compute_tf
    assert 'name = "ROLLOUT_DRILL_FAULT_PATHS", value = "/ready"' in compute_tf


def test_every_long_running_ecs_service_has_circuit_breaker_rollback() -> None:
    workload_jobs_tf = _read("infra/app/workload_jobs.tf")
    observability_tf = _read("infra/app/observability.tf")

    services = [
        (workload_jobs_tf, "order_event_consumer"),
        (observability_tf, "loki"),
        (observability_tf, "prometheus"),
        (observability_tf, "tempo"),
        (observability_tf, "grafana"),
    ]

    for terraform, service_name in services:
        service = _resource_block(terraform, "aws_ecs_service", service_name)
        assert "deployment_circuit_breaker" in service
        assert "enable   = true" in service
        assert "rollback = true" in service


def test_github_actions_role_can_apply_runtime_config_and_kms_resources() -> None:
    platform_iam = _read("infra/platform/github_actions.tf")

    assert (
        'runtime_config_bucket_name = "${local.name}-runtime-config-${local.account_id}"'
        in platform_iam
    )
    assert "RuntimeConfigBucketManage" in platform_iam
    assert "RuntimeConfigObjectsManage" in platform_iam
    assert "local.github_actions_runtime_config_bucket_resources" in platform_iam
    assert "local.github_actions_runtime_config_object_resources" in platform_iam

    assert "KMSCreateTaggedAppKeys" in platform_iam
    assert '"kms:CreateKey"' in platform_iam
    assert '"kms:TagResource"' in platform_iam
    assert "KMSManageTaggedAppKeys" in platform_iam
    assert "KMSManageStackAliases" in platform_iam
    assert '"iam:CreatePolicyVersion", "iam:DeletePolicyVersion"' in platform_iam
    assert '"iam:SetDefaultPolicyVersion"' in platform_iam
    assert "local.github_actions_sns_resources" in platform_iam
    assert "SNSManage" in platform_iam
    assert '"sns:CreateTopic"' in platform_iam
    assert '"sns:GetSubscriptionAttributes"' in platform_iam
    assert '"sns:Subscribe"' in platform_iam


def test_app_target_5xx_alarm_is_fast_enough_for_rollback_drills() -> None:
    edge_tf = _read("infra/app/edge.tf")
    alarm_start = edge_tf.index(
        'resource "aws_cloudwatch_metric_alarm" "app_target_5xx"'
    )
    latency_alarm_start = edge_tf.index(
        'resource "aws_cloudwatch_metric_alarm" "app_target_latency"'
    )
    alarm = edge_tf[alarm_start:latency_alarm_start]

    assert 'metric_name         = "HTTPCode_Target_5XX_Count"' in alarm
    assert "period              = 60" in alarm


def test_app_rollback_drill_uses_ecs_automatic_rollback() -> None:
    workflow = _read(".github/workflows/app-rollback-drill.yml")
    fault_helper = _read("scripts/ci/ci_set_app_drill_fault.py")

    assert "fault_mode:" in workflow
    assert "ci_set_app_drill_fault.py" in workflow
    assert "ROLLOUT_DRILL_FAULT_MODE" in fault_helper
    assert 'ECS_DEPLOY_WAIT_FOR_STABLE: "false"' in workflow
    assert "traffic_deadline=$((SECONDS + 720))" in workflow
    assert "rollback_deadline=$((SECONDS + 1200))" in workflow
    assert "Wait for ECS automatic rollback" in workflow
    assert "Bad drill revision completed instead of being rolled back" in workflow
    assert "Roll back to captured task definition" not in workflow
    assert (
        'ci_deploy_ecs_service.sh "${{ env.STACK_NAME }}" app "${{ steps.current.outputs.task_definition }}"'
        not in workflow
    )
    assert "aws ecs update-service" not in workflow


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


def test_operator_scripts_resolve_repo_root_from_script_path() -> None:
    for path in [
        "scripts/operator/db_exec.sh",
        "scripts/operator/db_seed_tunnel.sh",
        "scripts/operator/db_tunnel.sh",
        "scripts/operator/grafana_tunnel.sh",
        "scripts/operator/loki_tunnel.sh",
    ]:
        script = _read(path)

        assert 'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"' in script
        assert 'ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"' in script
        assert 'cd "$ROOT_DIR"' in script
        assert "20 20 12" not in script
        assert 'dirname "-e"' not in script


def test_cloud_changing_release_paths_stay_in_reviewed_workflows() -> None:
    makefile = _read("Makefile")
    docs = _read("docs/observability.md")
    app_build = _read(".github/workflows/app-build.yml")
    app_deploy = _read(".github/workflows/app-deploy.yml")

    removed_targets = [
        "-".join(("app", "build", "push")),
        "-".join(("app", "roll")),
        "-".join(("firelens", "build", "push")),
        "-".join(("firelens", "roll")),
    ]
    removed_scripts = [
        "_".join(("build", "push", "app")) + ".py",
        "_".join(("roll", "app", "image")) + ".py",
        "_".join(("build", "push", "firelens")) + ".py",
        "_".join(("roll", "firelens", "image")) + ".py",
    ]

    for removed in [*removed_targets, *removed_scripts]:
        assert removed not in makefile
        assert removed not in docs

    assert "observability/firelens/Dockerfile" in app_build
    assert "apps/api/Dockerfile" in app_build
    assert "firelens:${TAG}" in app_build
    assert "firelens:${IMAGE_TAG}" in app_deploy
    assert "verify_post_deploy.py" in app_deploy
    assert app_build.count("if: ${{ !github.event.repository.private }}") == 7


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


def test_release_evidence_events_are_emitted_by_cloud_changing_workflows() -> None:
    docs = _read("docs/observability.md")
    event_script = _read("scripts/observability/release_event.py")
    evidence_script = _read("scripts/observability/incident_evidence_bundle.py")
    dashboard = json.loads(_read("observability/grafana/dashboards/app-overview.json"))
    workflows = {
        "app_deploy": _read(".github/workflows/app-deploy.yml"),
        "app_rollback_drill": _read(".github/workflows/app-rollback-drill.yml"),
        "data_runtime_rollback_drill": _read(
            ".github/workflows/data-runtime-rollback-drill.yml"
        ),
        "infra_apply": _read(".github/workflows/infra-apply.yml"),
    }

    assert "release-event.json" in event_script
    assert "release-event.jsonl" in event_script
    assert "release-event.md" in event_script
    assert "loki/api/v1/push" in event_script
    assert "capture_alarm_snapshot" in event_script
    assert "--loki-push-best-effort" in event_script
    assert "--include-alarms" in event_script
    assert "release evidence events" in docs
    assert "JSONL artifacts" in docs
    assert "Delivery Events" in docs
    assert "dashboard annotations" in docs
    assert "CloudWatch alarm" in docs
    assert "LOKI_PUSH_URL" in docs
    assert "RELEASE_EVENTS_DIR" in docs
    assert "release-evidence-*" in docs
    assert "release_events" in evidence_script
    assert "--release-events-dir" in evidence_script
    assert "--loki-url" in evidence_script
    assert "query_range" in evidence_script
    assert "loki_count" in evidence_script
    assert "LOKI_URL" in docs

    delivery_annotation = next(
        item
        for item in dashboard["annotations"]["list"]
        if item["name"] == "Delivery Events"
    )
    assert delivery_annotation["datasource"]["type"] == "loki"
    assert "event_type" in delivery_annotation["expr"]
    assert "infra_apply" in delivery_annotation["expr"]

    delivery_panel = next(
        panel for panel in dashboard["panels"] if panel["title"] == "Delivery Events"
    )
    assert delivery_panel["datasource"]["type"] == "loki"
    assert delivery_panel["type"] == "logs"
    delivery_query = delivery_panel["targets"][0]["expr"]
    assert "event_type" in delivery_query
    assert "app_deploy" in delivery_query
    assert "infra_apply" in delivery_query

    for event_type, workflow in workflows.items():
        assert "scripts/observability/release_event.py" in workflow
        assert f"--event-type {event_type}" in workflow
        assert "--include-alarms" in workflow
        assert "--push-loki" in workflow
        assert "--loki-push-best-effort" in workflow
        assert "LOKI_PUSH_URL" in workflow
        assert "LOKI_URL" in workflow
        assert "actions/upload-artifact" in workflow
        assert "release-evidence-" in workflow
        assert 'release-event.md >> "$GITHUB_STEP_SUMMARY"' in workflow


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
