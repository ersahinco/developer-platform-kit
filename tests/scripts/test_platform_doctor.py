from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from scripts.platform.doctor import doctor_results
from scripts.platform.doctor import operator_path_commands
from scripts.platform.doctor import print_results


@pytest.fixture(autouse=True)
def _stable_port_checks(monkeypatch) -> None:
    monkeypatch.setattr(
        "scripts.platform.doctor._port_is_available", lambda _port: True
    )


def _runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    name = " ".join(command)
    if command[:2] == ["docker", "ps"]:
        return subprocess.CompletedProcess(command, 1, "", "Cannot connect to Docker")
    if command[:3] == ["aws", "sts", "get-caller-identity"]:
        return subprocess.CompletedProcess(
            command, 254, "", "Unable to locate credentials"
        )
    return subprocess.CompletedProcess(command, 0, f"{name} ok", "")


def _github_auth_fail_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    if command[:3] == ["gh", "auth", "status"]:
        return subprocess.CompletedProcess(command, 1, "", "not logged in")
    return _runner(command)


def _compose_services_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    if command == ["docker", "compose", "port", "api", "8000"]:
        return subprocess.CompletedProcess(command, 0, "0.0.0.0:8000\n", "")
    if command == ["docker", "compose", "port", "pgbouncer", "5432"]:
        return subprocess.CompletedProcess(command, 0, "0.0.0.0:6432\n", "")
    return _runner(command)


def _compose_api_on_alternate_port_runner(
    command: list[str],
) -> subprocess.CompletedProcess[str]:
    if command == ["docker", "compose", "port", "api", "8000"]:
        return subprocess.CompletedProcess(command, 0, "0.0.0.0:18000\n", "")
    return _runner(command)


def _candidate_fail_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    if "scripts/platform/admission_check.py" in command:
        return subprocess.CompletedProcess(command, 1, "candidate invalid", "")
    return _runner(command)


def test_platform_doctor_reports_required_and_optional_surfaces(
    monkeypatch,
) -> None:
    monkeypatch.setattr("scripts.platform.doctor._tool_exists", lambda _name: True)

    results = doctor_results(cloud=True, runner=_runner)
    by_name = {result.name: result for result in results}

    assert by_name["uv"].status == "ok"
    assert by_name["docker daemon"].status == "fail"
    assert by_name["github auth"].status == "ok"
    assert by_name["aws identity"].status == "warn"
    assert by_name["workload readiness"].status == "ok"


def test_platform_doctor_fails_when_required_default_local_port_is_occupied(
    monkeypatch,
) -> None:
    monkeypatch.setattr("scripts.platform.doctor._tool_exists", lambda _name: True)
    monkeypatch.setattr(
        "scripts.platform.doctor._port_is_available", lambda _port: False
    )

    results = doctor_results(cloud=False, runner=_runner)
    by_name = {result.name: result for result in results}

    assert by_name["local api port"].status == "fail"
    assert by_name["local api port"].hint == (
        "free port 8000 or set APP_PORT=<free-port> "
        "LOCAL_API_BASE_URL=http://127.0.0.1:<free-port>"
    )
    assert by_name["local prometheus port"].status == "warn"
    assert by_name["local grafana port"].status == "warn"


def test_platform_doctor_allows_ports_owned_by_this_compose_project(
    monkeypatch,
) -> None:
    monkeypatch.setattr("scripts.platform.doctor._tool_exists", lambda _name: True)
    monkeypatch.setattr(
        "scripts.platform.doctor._port_is_available", lambda _port: False
    )

    results = doctor_results(cloud=False, runner=_compose_services_runner)
    by_name = {result.name: result for result in results}

    assert by_name["local api port"].status == "ok"
    assert by_name["local api port"].hint == "already owned by api"
    assert by_name["local pgbouncer port"].status == "ok"


def test_platform_doctor_still_fails_when_compose_service_uses_different_host_port(
    monkeypatch,
) -> None:
    monkeypatch.setattr("scripts.platform.doctor._tool_exists", lambda _name: True)
    monkeypatch.setattr(
        "scripts.platform.doctor._port_is_available", lambda _port: False
    )

    results = doctor_results(cloud=False, runner=_compose_api_on_alternate_port_runner)
    by_name = {result.name: result for result in results}

    assert by_name["local api port"].status == "fail"


def test_platform_doctor_warns_on_github_auth_for_local_path(monkeypatch) -> None:
    monkeypatch.setattr("scripts.platform.doctor._tool_exists", lambda _name: True)

    results = doctor_results(cloud=False, runner=_github_auth_fail_runner)
    by_name = {result.name: result for result in results}

    assert by_name["github auth"].status == "warn"
    assert "run gh auth login" in by_name["github auth"].hint


def test_platform_doctor_requires_github_auth_for_cloud_path(monkeypatch) -> None:
    monkeypatch.setattr("scripts.platform.doctor._tool_exists", lambda _name: True)

    results = doctor_results(cloud=True, runner=_github_auth_fail_runner)
    by_name = {result.name: result for result in results}

    assert by_name["github auth"].status == "fail"


def test_platform_doctor_skips_candidate_schema_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("WORKLOAD_CANDIDATE", raising=False)
    monkeypatch.setattr("scripts.platform.doctor._tool_exists", lambda _name: True)

    results = doctor_results(cloud=False, runner=_runner)

    assert "workload candidate schema" not in {result.name for result in results}


def test_platform_doctor_checks_candidate_schema_when_set(monkeypatch) -> None:
    monkeypatch.setenv(
        "WORKLOAD_CANDIDATE",
        "tests/fixtures/workloads/internal_service_good.json",
    )
    monkeypatch.setattr("scripts.platform.doctor._tool_exists", lambda _name: True)

    results = doctor_results(cloud=False, runner=_runner)
    by_name = {result.name: result for result in results}

    assert by_name["workload candidate schema"].status == "ok"


def test_platform_doctor_fails_when_candidate_schema_fails(monkeypatch) -> None:
    monkeypatch.setenv(
        "WORKLOAD_CANDIDATE",
        "tests/fixtures/workloads/internal_service_bad.json",
    )
    monkeypatch.setattr("scripts.platform.doctor._tool_exists", lambda _name: True)

    results = doctor_results(cloud=False, runner=_candidate_fail_runner)
    by_name = {result.name: result for result in results}

    assert by_name["workload candidate schema"].status == "fail"
    assert (
        by_name["workload candidate schema"].hint
        == "run WORKLOAD_CANDIDATE=<path> make workload-admission-check: candidate invalid"
    )


def test_platform_doctor_marks_missing_required_tools_as_fail(monkeypatch) -> None:
    monkeypatch.setattr(
        "scripts.platform.doctor._tool_exists",
        lambda name: name not in {"gh", "jq", "terraform"},
    )

    results = doctor_results(cloud=False, runner=_runner)
    by_name = {result.name: result for result in results}

    assert by_name["gh"].status == "warn"
    assert by_name["jq"].status == "fail"
    assert by_name["terraform"].status == "warn"


def test_platform_doctor_uses_conftest_docker_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        "scripts.platform.doctor._tool_exists",
        lambda name: name != "conftest",
    )

    results = doctor_results(cloud=False, runner=_runner)
    by_name = {result.name: result for result in results}

    assert by_name["conftest"].status == "ok"
    assert (
        by_name["conftest"].hint == "Docker fallback available through make lint-policy"
    )


def test_platform_doctor_checkov_hint_matches_makefile(monkeypatch) -> None:
    monkeypatch.setattr(
        "scripts.platform.doctor._tool_exists",
        lambda name: name != "checkov",
    )

    results = doctor_results(cloud=False, runner=_runner)
    by_name = {result.name: result for result in results}

    assert by_name["checkov"].status == "warn"
    assert by_name["checkov"].hint == "install Checkov for make lint-infra"


def test_platform_doctor_output_is_short_and_actionable(capsys, monkeypatch) -> None:
    monkeypatch.setattr("scripts.platform.doctor._tool_exists", lambda _name: True)

    print_results(
        [
            doctor_results(cloud=True, runner=_runner)[0],
        ]
    )

    captured = capsys.readouterr()

    assert captured.out.startswith("ok")
    assert "\n\n" not in captured.out
    assert "next operator path: docs/operator-day-2.md" in captured.out


def test_platform_doctor_next_steps_match_operator_day_2() -> None:
    operator_day_2 = Path("docs/operator-day-2.md").read_text(encoding="utf-8")

    for command in operator_path_commands(cloud=True):
        assert command in operator_day_2

    assert "make platform-toolkit-validate-local" in operator_path_commands(cloud=False)
