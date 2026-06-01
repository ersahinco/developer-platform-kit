from __future__ import annotations

from pathlib import Path
import subprocess

from scripts.platform.doctor import doctor_results
from scripts.platform.doctor import operator_path_commands
from scripts.platform.doctor import print_results


def _runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    name = " ".join(command)
    if command[:2] == ["docker", "ps"]:
        return subprocess.CompletedProcess(command, 1, "", "Cannot connect to Docker")
    if command[:3] == ["aws", "sts", "get-caller-identity"]:
        return subprocess.CompletedProcess(
            command, 254, "", "Unable to locate credentials"
        )
    return subprocess.CompletedProcess(command, 0, f"{name} ok", "")


def _candidate_fail_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    if "scripts/platform/workload_fit_check.py" in command:
        return subprocess.CompletedProcess(command, 1, "fit: no", "")
    return _runner(command)


def test_platform_doctor_reports_required_and_optional_surfaces(
    monkeypatch,
) -> None:
    monkeypatch.setattr("scripts.platform.doctor._tool_exists", lambda _name: True)

    results = doctor_results(cloud=True, runner=_runner)
    by_name = {result.name: result for result in results}

    assert by_name["uv"].status == "ok"
    assert by_name["docker daemon"].status == "fail"
    assert by_name["aws identity"].status == "warn"
    assert by_name["workload readiness"].status == "ok"


def test_platform_doctor_skips_candidate_fit_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("WORKLOAD_CANDIDATE", raising=False)
    monkeypatch.setattr("scripts.platform.doctor._tool_exists", lambda _name: True)

    results = doctor_results(cloud=False, runner=_runner)

    assert "workload candidate fit" not in {result.name for result in results}


def test_platform_doctor_checks_candidate_fit_when_set(monkeypatch) -> None:
    monkeypatch.setenv(
        "WORKLOAD_CANDIDATE",
        "tests/fixtures/workloads/foreign_internal_service_good.json",
    )
    monkeypatch.setattr("scripts.platform.doctor._tool_exists", lambda _name: True)

    results = doctor_results(cloud=False, runner=_runner)
    by_name = {result.name: result for result in results}

    assert by_name["workload candidate fit"].status == "ok"


def test_platform_doctor_fails_when_candidate_fit_fails(monkeypatch) -> None:
    monkeypatch.setenv(
        "WORKLOAD_CANDIDATE",
        "tests/fixtures/workloads/foreign_internal_service_bad.json",
    )
    monkeypatch.setattr("scripts.platform.doctor._tool_exists", lambda _name: True)

    results = doctor_results(cloud=False, runner=_candidate_fail_runner)
    by_name = {result.name: result for result in results}

    assert by_name["workload candidate fit"].status == "fail"
    assert (
        by_name["workload candidate fit"].hint
        == "run WORKLOAD_CANDIDATE=<path> make workload-fit-check: fit: no"
    )


def test_platform_doctor_marks_missing_required_tools_as_fail(monkeypatch) -> None:
    monkeypatch.setattr(
        "scripts.platform.doctor._tool_exists",
        lambda name: name not in {"jq", "terraform"},
    )

    results = doctor_results(cloud=False, runner=_runner)
    by_name = {result.name: result for result in results}

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
