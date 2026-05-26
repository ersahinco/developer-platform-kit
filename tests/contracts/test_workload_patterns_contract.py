from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def _load_workloads() -> list[dict[str, Any]]:
    return json.loads((ROOT / "platform" / "workloads.json").read_text())["workloads"]


def _load_patterns() -> list[dict[str, Any]]:
    return json.loads((ROOT / "platform" / "workload-patterns.json").read_text())[
        "patterns"
    ]


def _value_at_path(payload: dict[str, Any], dotted_path: str) -> Any | None:
    current: Any = payload
    for segment in dotted_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current


def test_workload_patterns_are_declared_as_stable_center_contract() -> None:
    patterns = _load_patterns()

    assert [pattern["name"] for pattern in patterns] == [
        "edge-service",
        "internal-async-service",
        "operator-job",
        "scheduled-job",
        "export-job",
    ]
    assert all(isinstance(pattern["description"], str) for pattern in patterns)


def test_workloads_reference_only_declared_patterns() -> None:
    workloads = _load_workloads()
    declared_patterns = {pattern["name"] for pattern in _load_patterns()}

    for workload in workloads:
        patterns = workload["patterns"]
        assert isinstance(patterns, list)
        assert patterns
        assert set(patterns).issubset(declared_patterns)


def test_pattern_contract_required_fields_are_present_on_workloads() -> None:
    workloads = _load_workloads()
    patterns_by_name = {str(pattern["name"]): pattern for pattern in _load_patterns()}

    for workload in workloads:
        for pattern_name in workload["patterns"]:
            pattern = patterns_by_name[pattern_name]
            assert workload["kind"] == pattern["kind"]
            assert workload["operational"]["class"] == pattern["operational_class"]
            for required_field in pattern["required_fields"]:
                assert _value_at_path(workload, required_field) is not None
