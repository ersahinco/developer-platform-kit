from __future__ import annotations

from dataclasses import asdict
import json
import subprocess

from scripts.platform.capability_live_proof import run_live_proof


class _Ports:
    def __init__(self) -> None:
        self.next_port = 18000

    def __call__(self) -> int:
        value = self.next_port
        self.next_port += 1
        return value


class _FakeRuntime:
    def __init__(self, *, metrics_body: str | None = None) -> None:
        self.events: list[tuple[str, str]] = []
        self.envs: list[dict[str, str]] = []
        self.metrics_body = metrics_body or (
            'workload_info{workload="api",workload_class="edge-service"} 1.0\n'
            'http_requests_total{method="GET",route="/health",status_code="200"} 1.0\n'
        )

    def runner(
        self,
        args: list[str],
        env: dict[str, str],
    ) -> subprocess.CompletedProcess[str]:
        command = " ".join(args)
        self.events.append(("cmd", command))
        self.envs.append(dict(env))
        if "ps --services --status running" in command:
            return subprocess.CompletedProcess(
                args,
                0,
                "\n".join(
                    [
                        "db",
                        "pgbouncer",
                        "api",
                        "prometheus",
                        "loki",
                        "tempo",
                        "promtail",
                        "grafana",
                    ]
                ),
                "",
            )
        if "logs --no-log-prefix api" in command:
            return subprocess.CompletedProcess(
                args,
                0,
                "\n".join(
                    [
                        json.dumps(
                            {
                                "event": "http_request",
                                "route": "/admin/read-mode",
                                "auth_status": "denied",
                            }
                        ),
                        json.dumps(
                            {
                                "event": "http_request",
                                "route": "/admin/read-mode",
                                "auth_status": "succeeded",
                            }
                        ),
                    ]
                ),
                "",
            )
        return subprocess.CompletedProcess(args, 0, "", "")

    def http_text(
        self,
        url: str,
        method: str,
        headers: dict[str, str] | None,
        body: bytes | None,
        timeout: float,
    ) -> tuple[int, str, str]:
        del method, body, timeout
        self.events.append(("http", url))
        if url.endswith("/health"):
            return 200, "application/json", '{"status":"ok"}'
        if url.endswith("/ready"):
            return 200, "application/json", '{"status":"ready"}'
        if url.endswith("/metrics"):
            return 200, "text/plain; version=0.0.4", self.metrics_body
        if url.endswith("/admin/read-mode"):
            if headers == {"Authorization": "Bearer secret-token"}:
                return 200, "application/json", '{"mode":"legacy"}'
            return 401, "application/json", '{"detail":"Unauthorized"}'
        if url.endswith("/api/health"):
            return 200, "application/json", '{"database":"ok"}'
        if url.endswith("/ready"):
            return 200, "text/plain", "ready"
        if "/api/v1/query" in url:
            return 200, "application/json", json.dumps({"data": {"result": [{}]}})
        return 200, "text/plain", "ready"


def _run_fake(*, keep_stack: bool = False, metrics_body: str | None = None):
    runtime = _FakeRuntime(metrics_body=metrics_body)
    result = run_live_proof(
        project_name="proof-test",
        token="secret-token",
        keep_stack=keep_stack,
        timeout_seconds=1,
        runner=runtime.runner,
        http_text=runtime.http_text,
        port_allocator=_Ports(),
    )
    return runtime, result


def test_live_proof_runs_migrations_before_api_probes_and_cleans_up() -> None:
    runtime, result = _run_fake()

    commands = [value for kind, value in runtime.events if kind == "cmd"]
    http_urls = [value for kind, value in runtime.events if kind == "http"]

    assert commands[0].endswith("build api liquibase")
    assert any(
        "run --rm --remove-orphans liquibase update" in item for item in commands
    )
    migration_index = next(
        index
        for index, item in enumerate(runtime.events)
        if "liquibase update" in item[1]
    )
    first_health_index = next(
        index
        for index, item in enumerate(runtime.events)
        if item[1].endswith("/health")
    )
    assert migration_index < first_health_index
    assert http_urls[0].endswith("/health")
    assert commands[-1].endswith("down -v --remove-orphans")
    assert result.kept_stack is False
    assert {check.status for check in result.checks} == {"ok"}


def test_live_proof_passes_token_to_compose_without_leaking_it_to_result() -> None:
    runtime, result = _run_fake()

    assert any(env["PRIMARY_EDGE_AUTH_TOKEN"] == "secret-token" for env in runtime.envs)
    rendered = json.dumps(asdict(result))

    assert "secret-token" not in rendered
    assert result.project_name == "proof-test"
    assert result.runtime_target == "local-compose"


def test_live_proof_records_expected_capability_areas_and_checks() -> None:
    _runtime, result = _run_fake()

    checks = {(check.area, check.name): check for check in result.checks}

    assert ("network", "API health is reachable") in checks
    assert ("network", "API readiness proves DB connectivity") in checks
    assert ("authn", "protected endpoint rejects missing token") in checks
    assert ("authn", "protected endpoint rejects wrong token") in checks
    assert ("authn", "protected endpoint accepts configured bearer token") in checks
    assert ("authn", "api logs include denied and succeeded auth evidence") in checks
    assert ("observability", "API metrics endpoint is reachable") in checks
    assert ("observability", "Prometheus scraped workload_info") in checks
    assert ("observability", "Loki readiness is reachable") in checks
    assert ("observability", "Tempo readiness is reachable") in checks
    assert ("observability", "Grafana health is reachable") in checks
    assert ("service_identity", "Compose service identities are running") in checks
    assert ("secrets", "run migrations with local DB credentials") in checks


def test_live_proof_keep_stack_skips_cleanup() -> None:
    runtime, result = _run_fake(keep_stack=True)

    commands = [value for kind, value in runtime.events if kind == "cmd"]

    assert result.kept_stack is True
    assert not any(command.endswith("down -v --remove-orphans") for command in commands)


def test_live_proof_returns_failed_check_when_required_live_evidence_is_missing() -> (
    None
):
    _runtime, result = _run_fake(metrics_body="http_requests_total 1.0\n")

    failed = [check for check in result.checks if check.status == "fail"]

    assert any(check.name == "metrics include workload_info" for check in failed)
