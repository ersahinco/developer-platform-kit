from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import scripts.observability.verify_observability_delivery as delivery  # noqa: E402
import scripts.observability.generate_cloud_traffic as cloud_traffic  # noqa: E402
import scripts.observability.run_observability_cloud_jobs as cloud_jobs  # noqa: E402


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


def test_delivery_verifier_default_loki_freshness_skips_quiet_grafana(
    monkeypatch,
) -> None:
    expected_groups = delivery._expected_loki_log_group_names("aws-sdlc-containers")
    queried_log_groups: list[str] = []

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
            params = kwargs["params"]
            assert isinstance(params, dict)
            query = str(params["query"])
            queried_log_groups.append(query)
            return FakeResponse({"data": {"result": [{"stream": {}, "values": []}]}})
        raise AssertionError(f"unexpected Loki URL: {url}")

    monkeypatch.setattr(delivery.httpx, "get", fake_get)
    monkeypatch.delenv("LOKI_FRESH_LOG_GROUPS", raising=False)
    monkeypatch.setenv("LOKI_URL", "http://127.0.0.1:3100")

    results = delivery._check_loki_delivery("aws-sdlc-containers")

    assert all(result.ok for result in results)
    assert any("/ecs/aws-sdlc-containers/app" in item for item in queried_log_groups)
    assert any("/ecs/aws-sdlc-containers/loki" in item for item in queried_log_groups)
    assert not any(
        "/ecs/aws-sdlc-containers/grafana" in item for item in queried_log_groups
    )


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
                        "http_requests_total 1\nhttp_request_duration_seconds_count 1\n"
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


def test_cloud_job_waiter_finishes_when_container_exit_code_is_available(
    monkeypatch,
) -> None:
    calls = 0

    def fake_aws_json(args: list[str], region: str) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        assert args[:2] == ["ecs", "describe-tasks"]
        return {
            "tasks": [
                {
                    "lastStatus": "DEPROVISIONING",
                    "desiredStatus": "STOPPED",
                    "containers": [
                        {
                            "name": "liquibase",
                            "lastStatus": "STOPPED",
                            "exitCode": 0,
                        }
                    ],
                }
            ]
        }

    monkeypatch.setattr(cloud_jobs, "_aws_json", fake_aws_json)
    monkeypatch.setattr(
        cloud_jobs.time,
        "sleep",
        lambda seconds: (_ for _ in ()).throw(
            AssertionError("waiter slept after exit code was available")
        ),
    )

    cloud_jobs._wait_task_finished(
        "cluster",
        "arn:aws:ecs:region:acct:task/cluster/123",
        "liquibase",
        "eu-central-1",
        "liquibase",
    )

    assert calls == 1
