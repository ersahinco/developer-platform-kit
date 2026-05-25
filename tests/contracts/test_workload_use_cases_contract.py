from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_workloads_declare_target_neutral_use_cases() -> None:
    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())

    for workload in contract["workloads"]:
        use_cases = workload["use_cases"]

        assert isinstance(use_cases, list)
        assert use_cases
        assert all(isinstance(use_case, str) for use_case in use_cases)
        assert all("-" in use_case or use_case.isalnum() for use_case in use_cases)


def test_current_workloads_cover_multiple_platform_use_case_shapes() -> None:
    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())
    declared_use_cases = {
        use_case
        for workload in contract["workloads"]
        for use_case in workload["use_cases"]
    }

    assert "http-api" in declared_use_cases
    assert "event-consumer" in declared_use_cases
    assert "operator-task" in declared_use_cases
    assert "scheduled-pipeline" in declared_use_cases
