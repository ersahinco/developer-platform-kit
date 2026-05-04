from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.verify_observability_delivery as delivery  # noqa: E402
import scripts.generate_cloud_traffic as cloud_traffic  # noqa: E402
import scripts.run_observability_cloud_jobs as cloud_jobs  # noqa: E402


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
    tunnel_script = _read("scripts/loki_tunnel.sh")
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
    build_script = _read("scripts/build_push_firelens.py")
    roll_script = _read("scripts/roll_firelens_image.py")

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
    build_script = _read("scripts/build_push_app.py")
    roll_script = _read("scripts/roll_app_image.py")

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
    probe_script = _read("scripts/run_observability_cloud_jobs.py")

    assert "scripts/generate_cloud_traffic.py" in makefile
    assert "scripts/run_observability_cloud_jobs.py" in makefile
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


def test_delivery_verifier_checks_expected_inventory_and_rejects_stale_streams(
    monkeypatch,
) -> None:
    expected_groups = delivery._expected_log_group_names("aws-sdlc-containers")

    def fake_aws_json(args: list[str], region: str) -> dict[str, Any]:
        assert region == "eu-central-1"
        if args[:2] == ["logs", "describe-log-groups"]:
            return {
                "logGroups": [
                    {"logGroupName": name, "retentionInDays": 14}
                    for name in expected_groups
                ]
            }
        if args[:2] == ["logs", "describe-log-streams"]:
            return {
                "logStreams": [
                    {
                        "logStreamName": "firelens/app",
                        "lastEventTimestamp": 1_800_000_000_000,
                    }
                ]
            }
        raise AssertionError(f"unexpected AWS call: {args}")

    monkeypatch.setattr(delivery, "_aws_json", fake_aws_json)
    monkeypatch.setattr(delivery.time, "time", lambda: 1_800_000_100)
    monkeypatch.setenv("CLOUDWATCH_FRESH_LOG_GROUPS", "app")
    monkeypatch.setenv("CLOUDWATCH_LOG_FRESHNESS_SECONDS", "3600")

    inventory = delivery._check_cloudwatch_log_inventory(
        "aws-sdlc-containers", "eu-central-1"
    )
    freshness = delivery._check_cloudwatch_freshness(
        "aws-sdlc-containers", "eu-central-1"
    )

    assert all(result.ok for result in inventory)
    assert all(result.ok for result in freshness)


def test_delivery_verifier_flags_unexpected_stack_log_group(monkeypatch) -> None:
    expected_groups = delivery._expected_log_group_names("aws-sdlc-containers")

    def fake_aws_json(args: list[str], region: str) -> dict[str, Any]:
        return {
            "logGroups": [
                {"logGroupName": name, "retentionInDays": 14}
                for name in [*expected_groups, "/ecs/aws-sdlc-containers/old-worker"]
            ]
        }

    monkeypatch.setattr(delivery, "_aws_json", fake_aws_json)

    results = delivery._check_cloudwatch_log_inventory(
        "aws-sdlc-containers", "eu-central-1"
    )

    assert not all(result.ok for result in results)
    assert any("unexpected stack log groups" in result.message for result in results)


def test_delivery_verifier_checks_loki_log_group_labels_and_fresh_logs(
    monkeypatch,
) -> None:
    expected_groups = delivery._expected_loki_log_group_names("aws-sdlc-containers")

    class FakeResponse:
        status_code = 200

        def __init__(self, payload: dict[str, Any]) -> None:
            self._payload = payload

        def json(self) -> dict[str, Any]:
            return self._payload

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/loki/api/v1/series"):
            return FakeResponse(
                {"data": [{"log_group": log_group} for log_group in expected_groups]}
            )
        if url.endswith("/loki/api/v1/query_range"):
            return FakeResponse({"data": {"result": [{"stream": {}, "values": []}]}})
        raise AssertionError(f"unexpected Loki URL: {url}")

    monkeypatch.setattr(delivery.httpx, "get", fake_get)
    monkeypatch.setattr(delivery.time, "time", lambda: 1_800_000_100)
    monkeypatch.setenv("LOKI_FRESH_LOG_GROUPS", "app")

    results = delivery._check_loki_delivery("aws-sdlc-containers")

    assert all(result.ok for result in results)


def test_delivery_verifier_flags_old_loki_schema_without_log_group(
    monkeypatch,
) -> None:
    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, Any]:
            return {
                "data": [
                    {
                        "stack": "aws-sdlc-containers",
                        "environment": "aws",
                        "service": "app",
                        "container": "app",
                    }
                ]
            }

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        assert url.endswith("/loki/api/v1/series")
        return FakeResponse()

    monkeypatch.setattr(delivery.httpx, "get", fake_get)
    results = delivery._check_loki_log_group_inventory(
        "aws-sdlc-containers",
        "http://localhost:3100",
    )

    assert not all(result.ok for result in results)
    assert any(
        "old-schema streams without log_group" in result.message for result in results
    )


def test_delivery_verifier_normalizes_localhost_loki_url_to_ipv4() -> None:
    assert (
        delivery._normalized_loki_url("http://localhost:3100")
        == "http://127.0.0.1:3100"
    )
    assert (
        delivery._normalized_loki_url("http://localhost:3100/prefix")
        == "http://127.0.0.1:3100/prefix"
    )
    assert (
        delivery._normalized_loki_url("http://127.0.0.1:3100")
        == "http://127.0.0.1:3100"
    )


def test_cloud_traffic_generator_exercises_representative_api_paths(
    monkeypatch,
) -> None:
    calls: list[tuple[str, str]] = []

    class FakeResponse:
        def __init__(
            self,
            status_code: int,
            payload: dict[str, Any] | None = None,
            text: str = "",
        ) -> None:
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text
            self.headers = {"x-request-id": "test-request"}

        def json(self) -> dict[str, Any]:
            return self._payload

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def get(self, path: str) -> FakeResponse:
            calls.append(("GET", path))
            if path == "/customers/1":
                return FakeResponse(404)
            if path == "/orders/999999999":
                return FakeResponse(404)
            if path == "/metrics":
                return FakeResponse(
                    200,
                    text=(
                        "http_requests_total 1\n"
                        "http_request_duration_seconds_count 1\n"
                        "order_events_publish_total 1\n"
                    ),
                )
            return FakeResponse(200, {"mode": "legacy"})

        def post(
            self,
            path: str,
            *,
            json: dict[str, object],
            headers: dict[str, str],
        ) -> FakeResponse:
            calls.append(("POST", path))
            return FakeResponse(201, {"id": 123})

    monkeypatch.setenv("BASE_URL", "https://api.example.com")
    monkeypatch.setenv("ORDER_COUNT", "1")
    monkeypatch.delenv("CUSTOMER_ID", raising=False)
    monkeypatch.setenv("CUSTOMER_ID_CANDIDATES", "1,2")
    monkeypatch.setattr(cloud_traffic, "_token", lambda: "token")
    monkeypatch.setattr(cloud_traffic.httpx, "Client", FakeClient)
    monkeypatch.setattr(cloud_traffic.time, "sleep", lambda seconds: None)

    results = cloud_traffic.run()

    assert all(result.ok for result in results)
    assert calls == [
        ("GET", "/ready"),
        ("GET", "/admin/read-mode"),
        ("GET", "/admin/write-mode"),
        ("GET", "/customers/1"),
        ("GET", "/customers/2"),
        ("POST", "/orders"),
        ("GET", "/orders/123"),
        ("GET", "/orders/999999999"),
        ("GET", "/metrics"),
    ]


def test_cloud_traffic_generator_creates_fixture_customer_when_seed_data_is_absent(
    monkeypatch,
) -> None:
    calls: list[tuple[str, str]] = []

    class FakeResponse:
        def __init__(
            self,
            status_code: int,
            payload: dict[str, Any] | None = None,
            text: str = "",
        ) -> None:
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text
            self.headers = {"x-request-id": "test-request"}

        def json(self) -> dict[str, Any]:
            return self._payload

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def get(self, path: str) -> FakeResponse:
            calls.append(("GET", path))
            if path.startswith("/customers/"):
                return FakeResponse(404)
            if path == "/orders/999999999":
                return FakeResponse(404)
            if path == "/metrics":
                return FakeResponse(
                    200,
                    text=(
                        "http_requests_total 1\nhttp_request_duration_seconds_count 1\n"
                    ),
                )
            if path == "/orders/456":
                return FakeResponse(200, {"id": 456})
            return FakeResponse(200, {"mode": "legacy"})

        def post(
            self,
            path: str,
            *,
            json: dict[str, object] | None = None,
            headers: dict[str, str] | None = None,
        ) -> FakeResponse:
            calls.append(("POST", path))
            if path == "/admin/observability-fixture":
                return FakeResponse(200, {"id": 123})
            if path == "/orders":
                assert json is not None
                assert json["customer_id"] == 123
                assert headers is not None
                return FakeResponse(201, {"id": 456})
            raise AssertionError(f"unexpected POST: {path}")

    monkeypatch.setenv("BASE_URL", "https://api.example.com")
    monkeypatch.setenv("ORDER_COUNT", "1")
    monkeypatch.delenv("CUSTOMER_ID", raising=False)
    monkeypatch.setenv("CUSTOMER_ID_CANDIDATES", "1")
    monkeypatch.setattr(cloud_traffic, "_token", lambda: "token")
    monkeypatch.setattr(cloud_traffic.httpx, "Client", FakeClient)
    monkeypatch.setattr(cloud_traffic.time, "sleep", lambda seconds: None)

    results = cloud_traffic.run()

    assert all(result.ok for result in results)
    assert ("POST", "/admin/observability-fixture") in calls
    assert ("POST", "/orders") in calls


def test_cloud_job_probe_overrides_keep_batch_work_small(monkeypatch) -> None:
    monkeypatch.delenv("BACKFILL_MAX_BATCHES", raising=False)

    worker_override = cloud_jobs._worker_overrides()
    worker_env = worker_override["containerOverrides"][0]["environment"]
    assert {"name": "BACKFILL_MAX_BATCHES", "value": "1"} in worker_env
    assert {"name": "BACKFILL_SLEEP_MS", "value": "0"} in worker_env

    data_export_override = cloud_jobs._data_export_overrides()
    data_export_env = data_export_override["containerOverrides"][0]["environment"]
    assert any(item["name"] == "DATA_EXPORT_RUN_ID" for item in data_export_env)

    liquibase_override = cloud_jobs._liquibase_overrides()
    command = liquibase_override["containerOverrides"][0]["command"]
    assert "status" in command
    assert "update" not in command


def test_cloud_job_probe_runs_selected_targets(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    monkeypatch.setenv("OBSERVABILITY_CLOUD_JOB_TARGETS", "worker,prometheus")
    monkeypatch.setenv("OBSERVABILITY_RESTART_QUIET_DAEMONS", "true")
    monkeypatch.setattr(
        cloud_jobs,
        "_resolve_network",
        lambda stack_name, region: cloud_jobs.NetworkConfig(
            subnet_id="subnet-123",
            security_group_id="sg-123",
        ),
    )

    def fake_run_batch_target(**kwargs: object) -> cloud_jobs.ProbeResult:
        calls.append(("batch", str(kwargs["target"])))
        return cloud_jobs.ProbeResult(True, "batch", "ok")

    def fake_restart_service(
        cluster: str, service: str, region: str
    ) -> cloud_jobs.ProbeResult:
        calls.append(("service", service))
        return cloud_jobs.ProbeResult(True, "service", "ok")

    monkeypatch.setattr(cloud_jobs, "_run_batch_target", fake_run_batch_target)
    monkeypatch.setattr(cloud_jobs, "_restart_service", fake_restart_service)

    results = cloud_jobs.run()

    assert all(result.ok for result in results)
    assert calls == [("batch", "worker"), ("service", "prometheus")]
