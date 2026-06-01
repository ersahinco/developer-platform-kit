from __future__ import annotations

import subprocess

from scripts.platform.doctor import doctor_results
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


def test_platform_doctor_marks_missing_required_tools_as_fail(monkeypatch) -> None:
    monkeypatch.setattr(
        "scripts.platform.doctor._tool_exists",
        lambda name: name not in {"jq", "terraform"},
    )

    results = doctor_results(cloud=False, runner=_runner)
    by_name = {result.name: result for result in results}

    assert by_name["jq"].status == "fail"
    assert by_name["terraform"].status == "warn"


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
