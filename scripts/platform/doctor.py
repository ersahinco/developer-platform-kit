#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


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


def doctor_results(*, cloud: bool, runner: Runner = _run) -> list[CheckResult]:
    results: list[CheckResult] = []
    results.extend(
        [
            _tool_check("uv", required=True, hint="install uv"),
            _tool_check("docker", required=True, hint="install Docker Desktop"),
            _tool_check("jq", required=True, hint="install jq"),
            _tool_check("gh", required=True, hint="install GitHub CLI"),
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
    results.append(
        _command_check(
            "github auth",
            ["gh", "auth", "status"],
            runner=runner,
            required=True,
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

    cloud_tools = [
        ("aws", "install AWS CLI"),
        ("terraform", "install Terraform"),
        ("tflint", "install TFLint"),
        ("checkov", "install Checkov or use the Docker fallback targets"),
        ("conftest", "install Conftest or use the Docker fallback targets"),
    ]
    for name, hint in cloud_tools:
        results.append(_tool_check(name, required=False, hint=hint))

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


def print_results(results: list[CheckResult]) -> None:
    for result in results:
        line = f"{result.status:<4} {result.name}"
        if result.hint:
            line = f"{line}: {result.hint}"
        print(line)


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
    print_results(results)
    return 1 if any(result.status == "fail" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
