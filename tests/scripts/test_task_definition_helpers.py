from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _write_task_definition(path: Path, containers: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps({"containerDefinitions": containers}) + "\n",
        encoding="utf-8",
    )


def test_prepare_liquibase_task_definition_sets_command_and_firelens_image(
    tmp_path: Path,
) -> None:
    task_definition = tmp_path / "liquibase.json"
    _write_task_definition(
        task_definition,
        [
            {"name": "liquibase", "image": "old-liquibase"},
            {"name": "log-router", "image": "old-firelens"},
        ],
    )

    result = subprocess.run(
        [
            "python3",
            "scripts/ci/ci_prepare_liquibase_task_definition.py",
            str(task_definition),
            "example.com/firelens:sha-test",
        ],
        check=False,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    updated = json.loads(task_definition.read_text(encoding="utf-8"))
    containers = {item["name"]: item for item in updated["containerDefinitions"]}
    assert containers["liquibase"]["workingDirectory"] == "/liquibase"
    assert containers["liquibase"]["command"] == [
        "--search-path=/liquibase",
        "--changelog-file=changelog/db.changelog-master.yaml",
        "update",
    ]
    assert containers["log-router"]["image"] == "example.com/firelens:sha-test"


def test_prepare_liquibase_task_definition_requires_expected_containers(
    tmp_path: Path,
) -> None:
    task_definition = tmp_path / "liquibase.json"
    _write_task_definition(task_definition, [{"name": "liquibase"}])

    result = subprocess.run(
        [
            "python3",
            "scripts/ci/ci_prepare_liquibase_task_definition.py",
            str(task_definition),
            "example.com/firelens:sha-test",
        ],
        check=False,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "log-router container not found" in result.stderr


def test_set_app_drill_fault_merges_sorted_fault_environment(tmp_path: Path) -> None:
    task_definition = tmp_path / "app.json"
    _write_task_definition(
        task_definition,
        [
            {
                "name": "app",
                "environment": [
                    {"name": "EXISTING", "value": "kept"},
                    {"name": "ROLLOUT_DRILL_FAULT_MODE", "value": "off"},
                ],
            }
        ],
    )

    result = subprocess.run(
        [
            "python3",
            "scripts/ci/ci_set_app_drill_fault.py",
            str(task_definition),
            "latency",
        ],
        check=False,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    updated = json.loads(task_definition.read_text(encoding="utf-8"))
    environment = updated["containerDefinitions"][0]["environment"]
    assert environment == sorted(environment, key=lambda item: item["name"])
    values = {item["name"]: item["value"] for item in environment}
    assert values["EXISTING"] == "kept"
    assert values["ROLLOUT_DRILL_FAULT_MODE"] == "latency"
    assert values["ROLLOUT_DRILL_FAULT_PATHS"] == "/ready"
    assert values["ROLLOUT_DRILL_FAULT_DELAY_SECONDS"] == "3"
    assert values["ROLLOUT_DRILL_FAULT_STATUS_CODE"] == "503"


def test_set_app_drill_fault_requires_app_container(tmp_path: Path) -> None:
    task_definition = tmp_path / "app.json"
    _write_task_definition(task_definition, [{"name": "worker"}])

    result = subprocess.run(
        [
            "python3",
            "scripts/ci/ci_set_app_drill_fault.py",
            str(task_definition),
            "error",
        ],
        check=False,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "app container not found" in result.stderr
