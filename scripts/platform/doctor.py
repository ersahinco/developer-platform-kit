#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]

LOCAL_OPERATOR_PATH = (
    "make workload-readiness-check",
    "make platform-toolkit-smoke-local",
    "make platform-toolkit-validate-local",
)

CLOUD_OPERATOR_PATH = (
    "make workload-readiness-check",
    "make platform-toolkit-validate-cloud",
    "make workflow-dry-run-commands",
    "make release-evidence-runs",
    "GH_RUN_ID=<workflow-run-id> make release-evidence-download",
    "GH_RUN_ID=<workflow-run-id> make operator-payload-download",
    "GH_RUN_ID=<workflow-run-id> LOOKBACK_MINUTES=60 make incident-evidence",
)

LOCAL_PORTS = (
    ("local api port", "APP_PORT", 8000, "api", 8000, True),
    ("local postgres port", "POSTGRES_PORT", 5432, "db", 5432, True),
    ("local pgbouncer port", "PGBOUNCER_PORT", 6432, "pgbouncer", 5432, True),
    ("local redis port", "REDIS_PORT", 6379, "redis", 6379, True),
    ("local dapr http port", "DAPR_HTTP_PORT", 3500, "event-consumer-dapr", 3500, True),
    ("local prometheus port", "PROMETHEUS_PORT", 9090, "prometheus", 9090, False),
    ("local loki port", "LOKI_PORT", 3100, "loki", 3100, False),
    ("local tempo port", "TEMPO_PORT", 3200, "tempo", 3200, False),
    ("local tempo otlp http port", "TEMPO_OTLP_HTTP_PORT", 4318, "tempo", 4318, False),
    ("local tempo otlp grpc port", "TEMPO_OTLP_GRPC_PORT", 4317, "tempo", 4317, False),
    ("local grafana port", "GRAFANA_PORT", 3000, "grafana", 3000, False),
)


@dataclass(frozen=True)
class CheckResult:
    status: str
    name: str
    hint: str = ""


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _tool_exists(name: str) -> bool:
    return shutil.which(name) is not None


def _tool_check(name: str, *, required: bool, hint: str) -> CheckResult:
    if _tool_exists(name):
        return CheckResult("ok", name)
    status = "fail" if required else "warn"
    return CheckResult(status, name, hint)


def _tool_check_with_docker_fallback(name: str, *, fallback_target: str) -> CheckResult:
    if _tool_exists(name):
        return CheckResult("ok", name)
    if _tool_exists("docker"):
        return CheckResult(
            "ok", name, f"Docker fallback available through {fallback_target}"
        )
    return CheckResult(
        "warn", name, f"install {name} or use {fallback_target} with Docker"
    )


def _command_check(
    name: str,
    command: list[str],
    *,
    runner: Runner,
    required: bool,
    hint: str,
) -> CheckResult:
    try:
        completed = runner(command)
    except FileNotFoundError:
        completed = subprocess.CompletedProcess(command, 127, "", "not found")
    if completed.returncode == 0:
        return CheckResult("ok", name)
    status = "fail" if required else "warn"
    detail = _short_error(completed)
    return CheckResult(status, name, f"{hint}: {detail}" if detail else hint)


def _short_error(completed: subprocess.CompletedProcess[str]) -> str:
    text = (completed.stderr or completed.stdout).strip()
    if not text:
        return ""
    return text.splitlines()[0][:180]


def _repo_file_checks() -> list[CheckResult]:
    required_paths = [
        "platform/workloads.json",
        "platform/runtime-conformance.json",
        "compose.yaml",
        "Makefile",
        ".github/workflows/app-build.yml",
        ".github/workflows/app-deploy.yml",
        ".github/workflows/infra-plan.yml",
        ".github/workflows/operational-snapshot.yml",
    ]
    results = []
    for path in required_paths:
        if (ROOT / path).is_file():
            results.append(CheckResult("ok", path))
        else:
            results.append(CheckResult("fail", path, "restore expected repo file"))
    return results


def _port_is_available(port: int) -> bool:
    try:
        with socket.create_server(("0.0.0.0", port)):
            return True
    except OSError:
        return False


def _compose_published_host_ports(
    *,
    runner: Runner,
    service: str,
    container_port: int,
) -> set[int]:
    completed = runner(["docker", "compose", "port", service, str(container_port)])
    if completed.returncode != 0:
        return set()
    ports: set[int] = set()
    for line in completed.stdout.splitlines():
        value = line.strip()
        if not value or value.startswith("time="):
            continue
        try:
            ports.add(int(value.rsplit(":", 1)[1]))
        except IndexError, ValueError:
            continue
    return ports


def _local_port_checks(*, runner: Runner) -> list[CheckResult]:
    results: list[CheckResult] = []
    for name, env_var, default_port, service, container_port, required in LOCAL_PORTS:
        raw_port = os.environ.get(env_var, str(default_port))
        try:
            port = int(raw_port)
        except ValueError:
            results.append(
                CheckResult("fail", name, f"{env_var} must be a port number")
            )
            continue
        if _port_is_available(port):
            results.append(CheckResult("ok", name))
            continue
        published_ports = _compose_published_host_ports(
            runner=runner,
            service=service,
            container_port=container_port,
        )
        if port in published_ports:
            results.append(CheckResult("ok", name, f"already owned by {service}"))
            continue
        hint = f"free port {port} or set {env_var}=<free-port>"
        if env_var == "APP_PORT":
            hint = (
                "free port "
                f"{port} or set APP_PORT=<free-port> "
                "LOCAL_API_BASE_URL=http://127.0.0.1:<free-port>"
            )
        results.append(
            CheckResult(
                "fail" if required else "warn",
                name,
                hint,
            )
        )
    return results


def doctor_results(*, cloud: bool, runner: Runner = _run) -> list[CheckResult]:
    results: list[CheckResult] = []
    results.extend(
        [
            _tool_check("uv", required=True, hint="install uv"),
            _tool_check("docker", required=True, hint="install Docker Desktop"),
            _tool_check("jq", required=True, hint="install jq"),
            _tool_check("gh", required=cloud, hint="install GitHub CLI"),
        ]
    )
    results.extend(_repo_file_checks())

    results.append(
        _command_check(
            "docker compose",
            ["docker", "compose", "version"],
            runner=runner,
            required=True,
            hint="install Docker Compose plugin",
        )
    )
    results.append(
        _command_check(
            "docker daemon",
            ["docker", "ps"],
            runner=runner,
            required=True,
            hint="start Docker Desktop",
        )
    )
    results.extend(_local_port_checks(runner=runner))
    results.append(
        _command_check(
            "github auth",
            ["gh", "auth", "status"],
            runner=runner,
            required=cloud,
            hint="run gh auth login",
        )
    )
    results.append(
        _command_check(
            "workload readiness",
            [sys.executable, "scripts/platform/workload_readiness.py", "--check"],
            runner=runner,
            required=True,
            hint="run make workload-readiness-check",
        )
    )
    workload_candidate = os.environ.get("WORKLOAD_CANDIDATE")
    if workload_candidate:
        results.append(
            _command_check(
                "workload candidate fit",
                [
                    sys.executable,
                    "scripts/platform/workload_fit_check.py",
                    "--candidate",
                    workload_candidate,
                ],
                runner=runner,
                required=True,
                hint="run WORKLOAD_CANDIDATE=<path> make workload-fit-check",
            )
        )

    cloud_tools = [
        ("aws", "install AWS CLI"),
        ("terraform", "install Terraform"),
        ("tflint", "install TFLint"),
        ("checkov", "install Checkov for make lint-infra"),
    ]
    for name, hint in cloud_tools:
        results.append(_tool_check(name, required=False, hint=hint))
    results.append(
        _tool_check_with_docker_fallback("conftest", fallback_target="make lint-policy")
    )

    if cloud:
        results.append(
            _command_check(
                "aws identity",
                ["aws", "sts", "get-caller-identity"],
                runner=runner,
                required=False,
                hint="run aws sts get-caller-identity before cloud workflows",
            )
        )
        results.append(
            _command_check(
                "github workflows",
                ["gh", "workflow", "list", "--all", "--limit", "50"],
                runner=runner,
                required=False,
                hint="run gh auth status before workflow dry runs",
            )
        )
    return results


def operator_path_commands(*, cloud: bool) -> tuple[str, ...]:
    return CLOUD_OPERATOR_PATH if cloud else LOCAL_OPERATOR_PATH


def print_results(results: list[CheckResult], *, cloud: bool = False) -> None:
    for result in results:
        line = f"{result.status:<4} {result.name}"
        if result.hint:
            line = f"{line}: {result.hint}"
        print(line)
    print("next operator path: docs/operator-day-2.md")
    for command in operator_path_commands(cloud=cloud):
        print(f"next {command}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check local and optional cloud prerequisites for the delivery toolkit."
    )
    parser.add_argument(
        "--cloud",
        action="store_true",
        help="Also check cloud/operator credentials and workflow access.",
    )
    args = parser.parse_args()

    results = doctor_results(cloud=args.cloud)
    print_results(results, cloud=args.cloud)
    return 1 if any(result.status == "fail" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
