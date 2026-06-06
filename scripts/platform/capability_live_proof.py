#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import asdict
from dataclasses import dataclass
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
import uuid
from typing import Any
from urllib import error
from urllib import parse
from urllib import request


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_TARGET = "local-compose"
DRILL_SERVICES = (
    "db",
    "pgbouncer",
    "api",
    "prometheus",
    "loki",
    "tempo",
    "promtail",
    "grafana",
)
PORT_ENV_NAMES = (
    "APP_PORT",
    "POSTGRES_PORT",
    "PGBOUNCER_PORT",
    "PROMETHEUS_PORT",
    "LOKI_PORT",
    "TEMPO_PORT",
    "TEMPO_OTLP_HTTP_PORT",
    "TEMPO_OTLP_GRPC_PORT",
    "GRAFANA_PORT",
)


@dataclass(frozen=True)
class LiveCheck:
    area: str
    name: str
    status: str
    evidence: str


@dataclass(frozen=True)
class LiveProofResult:
    project_name: str
    runtime_target: str
    kept_stack: bool
    checks: list[LiveCheck]
    endpoints: dict[str, str]


CommandRunner = Callable[[list[str], dict[str, str]], subprocess.CompletedProcess[str]]
HttpText = Callable[
    [str, str, dict[str, str] | None, bytes | None, float],
    tuple[int, str, str],
]
PortAllocator = Callable[[], int]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run_command(
    args: list[str],
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def _http_text(
    url: str,
    method: str,
    headers: dict[str, str] | None,
    body: bytes | None,
    timeout: float,
) -> tuple[int, str, str]:
    req = request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return (
                response.status,
                response.headers.get("content-type", ""),
                response.read().decode("utf-8"),
            )
    except error.HTTPError as exc:
        return (
            exc.code,
            exc.headers.get("content-type", ""),
            exc.read().decode("utf-8"),
        )


def _project_name(value: str | None) -> str:
    if value:
        return value
    return f"capability-proof-local-live-{uuid.uuid4().hex[:8]}"


def _ports(allocator: PortAllocator) -> dict[str, int]:
    return {name: allocator() for name in PORT_ENV_NAMES}


def _compose_base(project_name: str) -> list[str]:
    return ["docker", "compose", "-p", project_name]


def _with_env(ports: dict[str, int], token: str, project_name: str) -> dict[str, str]:
    env = os.environ.copy()
    for name, port in ports.items():
        env[name] = str(port)
    env["PRIMARY_EDGE_AUTH_TOKEN"] = token
    env["OTEL_TRACES_ENABLED"] = "true"
    env["STACK_NAME"] = project_name
    return env


def _check_command(
    *,
    checks: list[LiveCheck],
    runner: CommandRunner,
    env: dict[str, str],
    args: list[str],
    area: str,
    name: str,
    evidence: str,
) -> bool:
    completed = runner(args, env)
    if completed.returncode == 0:
        checks.append(LiveCheck(area, name, "ok", evidence))
        return True
    detail = _short_error(completed)
    checks.append(
        LiveCheck(
            area,
            name,
            "fail",
            f"{evidence}; {detail}" if detail else evidence,
        )
    )
    return False


def _short_error(completed: subprocess.CompletedProcess[str]) -> str:
    text = (completed.stderr or completed.stdout).strip()
    if not text:
        return ""
    return text.splitlines()[0][:220]


def _wait_for_status(
    *,
    http_text: HttpText,
    checks: list[LiveCheck],
    area: str,
    name: str,
    url: str,
    expected_status: int,
    timeout_seconds: int,
    method: str = "GET",
    headers: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    deadline = time.monotonic() + timeout_seconds
    last: tuple[int, str, str] | None = None
    while time.monotonic() < deadline:
        try:
            status, content_type, body = http_text(url, method, headers, None, 2.0)
            last = (status, content_type, body)
            if status == expected_status:
                checks.append(LiveCheck(area, name, "ok", f"{url} returned {status}"))
                return status, content_type, body
        except OSError as exc:
            last = (0, "", str(exc))
        time.sleep(1)
    status, content_type, body = last or (0, "", "no response")
    checks.append(
        LiveCheck(
            area,
            name,
            "fail",
            f"{url} returned {status}, expected {expected_status}: {body[:220]}",
        )
    )
    return status, content_type, body


def _http_check(
    *,
    http_text: HttpText,
    checks: list[LiveCheck],
    area: str,
    name: str,
    url: str,
    expected_status: int,
    method: str = "GET",
    headers: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    status, content_type, body = http_text(url, method, headers, None, 5.0)
    if status == expected_status:
        checks.append(LiveCheck(area, name, "ok", f"{url} returned {status}"))
    else:
        checks.append(
            LiveCheck(
                area,
                name,
                "fail",
                f"{url} returned {status}, expected {expected_status}: {body[:220]}",
            )
        )
    return status, content_type, body


def _body_contains(
    checks: list[LiveCheck],
    *,
    area: str,
    name: str,
    body: str,
    needle: str,
    evidence: str,
) -> None:
    checks.append(
        LiveCheck(
            area,
            name,
            "ok" if needle in body else "fail",
            evidence if needle in body else f"missing {needle}",
        )
    )


def _json_dict(value: str) -> dict[str, Any]:
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return data


def _prometheus_query_url(base_url: str, query: str) -> str:
    return f"{base_url.rstrip('/')}/api/v1/query?{parse.urlencode({'query': query})}"


def _wait_for_prometheus_series(
    *,
    http_text: HttpText,
    checks: list[LiveCheck],
    url: str,
    timeout_seconds: int,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_count = 0
    query_url = _prometheus_query_url(url, "workload_info")
    while time.monotonic() < deadline:
        status, _content_type, body = http_text(query_url, "GET", None, None, 2.0)
        if status == 200:
            try:
                payload = _json_dict(body)
                last_count = len(payload.get("data", {}).get("result", []))
            except json.JSONDecodeError, ValueError, AttributeError:
                last_count = 0
            if last_count > 0:
                checks.append(
                    LiveCheck(
                        "observability",
                        "Prometheus scraped workload_info",
                        "ok",
                        f"workload_info_series={last_count}",
                    )
                )
                return
        time.sleep(1)
    checks.append(
        LiveCheck(
            "observability",
            "Prometheus scraped workload_info",
            "fail",
            f"workload_info_series={last_count}",
        )
    )


def _compose_logs(
    *,
    runner: CommandRunner,
    env: dict[str, str],
    project_name: str,
) -> subprocess.CompletedProcess[str]:
    return runner(
        [*_compose_base(project_name), "logs", "--no-log-prefix", "api"],
        env,
    )


def _structured_log_checks(
    *,
    checks: list[LiveCheck],
    logs: str,
) -> None:
    events: list[dict[str, Any]] = []
    for line in logs.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)

    http_events = [event for event in events if event.get("event") == "http_request"]
    checks.append(
        LiveCheck(
            "observability",
            "api logs include structured http_request events",
            "ok" if http_events else "fail",
            f"structured_events={len(http_events)}",
        )
    )
    auth_statuses = {
        event.get("auth_status")
        for event in http_events
        if event.get("route") == "/admin/read-mode"
    }
    checks.append(
        LiveCheck(
            "authn",
            "api logs include denied and succeeded auth evidence",
            "ok" if {"denied", "succeeded"}.issubset(auth_statuses) else "fail",
            "auth_status=denied,succeeded"
            if {"denied", "succeeded"}.issubset(auth_statuses)
            else f"auth_statuses={sorted(str(value) for value in auth_statuses)}",
        )
    )


def run_live_proof(
    *,
    project_name: str | None = None,
    token: str | None = None,
    keep_stack: bool = False,
    timeout_seconds: int = 90,
    runner: CommandRunner = _run_command,
    http_text: HttpText = _http_text,
    port_allocator: PortAllocator = _free_port,
) -> LiveProofResult:
    resolved_project_name = _project_name(project_name)
    resolved_token = token or secrets.token_urlsafe(24)
    ports = _ports(port_allocator)
    env = _with_env(ports, resolved_token, resolved_project_name)
    checks: list[LiveCheck] = []
    compose = _compose_base(resolved_project_name)
    endpoints = {
        "api": f"http://127.0.0.1:{ports['APP_PORT']}",
        "prometheus": f"http://127.0.0.1:{ports['PROMETHEUS_PORT']}",
        "loki": f"http://127.0.0.1:{ports['LOKI_PORT']}",
        "tempo": f"http://127.0.0.1:{ports['TEMPO_PORT']}",
        "grafana": f"http://127.0.0.1:{ports['GRAFANA_PORT']}",
    }

    try:
        _check_command(
            checks=checks,
            runner=runner,
            env=env,
            args=[*compose, "build", "api", "liquibase"],
            area="ci_cd",
            name="build proof images",
            evidence="docker compose build api liquibase",
        )
        _check_command(
            checks=checks,
            runner=runner,
            env=env,
            args=[*compose, "up", "-d", "--remove-orphans", "db", "pgbouncer"],
            area="network",
            name="start database services",
            evidence="db and pgbouncer started in isolated Compose project",
        )
        _check_command(
            checks=checks,
            runner=runner,
            env=env,
            args=[
                *compose,
                "--profile",
                "migration",
                "run",
                "--rm",
                "--remove-orphans",
                "liquibase",
                "update",
            ],
            area="secrets",
            name="run migrations with local DB credentials",
            evidence="liquibase update completed",
        )
        _check_command(
            checks=checks,
            runner=runner,
            env=env,
            args=[
                *compose,
                "--profile",
                "observability",
                "up",
                "-d",
                "--remove-orphans",
                "api",
                "prometheus",
                "loki",
                "tempo",
                "promtail",
                "grafana",
            ],
            area="network",
            name="start API and observability services",
            evidence="api,prometheus,loki,tempo,promtail,grafana started",
        )

        _wait_for_status(
            http_text=http_text,
            checks=checks,
            area="network",
            name="API health is reachable",
            url=f"{endpoints['api']}/health",
            expected_status=200,
            timeout_seconds=timeout_seconds,
        )
        _wait_for_status(
            http_text=http_text,
            checks=checks,
            area="network",
            name="API readiness proves DB connectivity",
            url=f"{endpoints['api']}/ready",
            expected_status=200,
            timeout_seconds=timeout_seconds,
        )

        _, metrics_content_type, metrics_body = _http_check(
            http_text=http_text,
            checks=checks,
            area="observability",
            name="API metrics endpoint is reachable",
            url=f"{endpoints['api']}/metrics",
            expected_status=200,
        )
        _body_contains(
            checks,
            area="observability",
            name="metrics are Prometheus text",
            body=metrics_content_type,
            needle="text/plain",
            evidence="content-type=text/plain",
        )
        _body_contains(
            checks,
            area="observability",
            name="metrics include workload_info",
            body=metrics_body,
            needle='workload_info{workload="api"',
            evidence='workload_info{workload="api"}',
        )
        _body_contains(
            checks,
            area="observability",
            name="metrics include request counter",
            body=metrics_body,
            needle="http_requests_total",
            evidence="http_requests_total",
        )

        _http_check(
            http_text=http_text,
            checks=checks,
            area="authn",
            name="protected endpoint rejects missing token",
            url=f"{endpoints['api']}/admin/read-mode",
            expected_status=401,
        )
        _http_check(
            http_text=http_text,
            checks=checks,
            area="authn",
            name="protected endpoint rejects wrong token",
            url=f"{endpoints['api']}/admin/read-mode",
            expected_status=401,
            headers={"Authorization": "Bearer wrong-token"},
        )
        _http_check(
            http_text=http_text,
            checks=checks,
            area="authn",
            name="protected endpoint accepts configured bearer token",
            url=f"{endpoints['api']}/admin/read-mode",
            expected_status=200,
            headers={"Authorization": f"Bearer {resolved_token}"},
        )

        _wait_for_status(
            http_text=http_text,
            checks=checks,
            area="observability",
            name="Loki readiness is reachable",
            url=f"{endpoints['loki']}/ready",
            expected_status=200,
            timeout_seconds=timeout_seconds,
        )
        _wait_for_status(
            http_text=http_text,
            checks=checks,
            area="observability",
            name="Tempo readiness is reachable",
            url=f"{endpoints['tempo']}/ready",
            expected_status=200,
            timeout_seconds=timeout_seconds,
        )
        _wait_for_status(
            http_text=http_text,
            checks=checks,
            area="observability",
            name="Grafana health is reachable",
            url=f"{endpoints['grafana']}/api/health",
            expected_status=200,
            timeout_seconds=timeout_seconds,
        )
        _wait_for_status(
            http_text=http_text,
            checks=checks,
            area="observability",
            name="Prometheus query API is reachable",
            url=_prometheus_query_url(endpoints["prometheus"], "workload_info"),
            expected_status=200,
            timeout_seconds=timeout_seconds,
        )
        _wait_for_prometheus_series(
            http_text=http_text,
            checks=checks,
            url=endpoints["prometheus"],
            timeout_seconds=timeout_seconds,
        )

        ps = runner([*compose, "ps", "--services", "--status", "running"], env)
        running = set(ps.stdout.splitlines()) if ps.returncode == 0 else set()
        missing = [service for service in DRILL_SERVICES if service not in running]
        checks.append(
            LiveCheck(
                "service_identity",
                "Compose service identities are running",
                "ok" if not missing else "fail",
                "services=" + ",".join(sorted(running))
                if not missing
                else "missing=" + ",".join(missing),
            )
        )

        logs = _compose_logs(runner=runner, env=env, project_name=resolved_project_name)
        if logs.returncode == 0:
            _structured_log_checks(checks=checks, logs=logs.stdout)
        else:
            checks.append(
                LiveCheck(
                    "observability",
                    "read API logs",
                    "fail",
                    _short_error(logs) or "docker compose logs api failed",
                )
            )
    except Exception as exc:  # noqa: BLE001
        checks.append(LiveCheck("runtime", "live proof execution", "fail", str(exc)))
    finally:
        if not keep_stack:
            completed = runner(
                [
                    *compose,
                    "--profile",
                    "observability",
                    "down",
                    "-v",
                    "--remove-orphans",
                ],
                env,
            )
            checks.append(
                LiveCheck(
                    "runtime",
                    "cleanup isolated Compose project",
                    "ok" if completed.returncode == 0 else "fail",
                    f"project={resolved_project_name}",
                )
            )

    return LiveProofResult(
        project_name=resolved_project_name,
        runtime_target=RUNTIME_TARGET,
        kept_stack=keep_stack,
        checks=checks,
        endpoints=endpoints,
    )


def _redacted_result(result: LiveProofResult) -> dict[str, Any]:
    return asdict(result)


def _print_text(result: LiveProofResult) -> None:
    print(f"project_name: {result.project_name}")
    print(f"runtime_target: {result.runtime_target}")
    print(f"kept_stack: {str(result.kept_stack).lower()}")
    for check in result.checks:
        print(f"{check.status:<4} {check.area} {check.name}: {check.evidence}")
    if result.kept_stack:
        print("inspection endpoints:")
        for name, url in result.endpoints.items():
            print(f"  {name}: {url}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a live local runtime capability proof in an isolated Compose project."
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--keep-stack", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--project-name")
    parser.add_argument("--token")
    args = parser.parse_args()

    result = run_live_proof(
        project_name=args.project_name,
        token=args.token,
        keep_stack=args.keep_stack,
        timeout_seconds=args.timeout_seconds,
    )
    if args.format == "json":
        print(json.dumps(_redacted_result(result), indent=2))
    else:
        _print_text(result)
    return 1 if any(check.status == "fail" for check in result.checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
