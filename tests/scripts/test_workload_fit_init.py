from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.platform.workload_fit_check import evaluate_candidate
from scripts.platform.workload_fit_init import build_candidate


ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_GENERATOR_KEYS = {
    "app_code",
    "chart",
    "crd",
    "deployment",
    "deployment_steps",
    "deploy",
    "files",
    "generated_files",
    "generates",
    "helm",
    "kustomization",
    "manifests",
    "resources",
    "runtime_resources",
    "scaffold",
    "templates",
    "terraform",
}


def _walk_keys(value: object) -> list[str]:
    if isinstance(value, dict):
        keys: list[str] = []
        for key, nested in value.items():
            keys.append(str(key))
            keys.extend(_walk_keys(nested))
        return keys
    if isinstance(value, list):
        keys = []
        for item in value:
            keys.extend(_walk_keys(item))
        return keys
    return []


def _assert_candidate_is_boundary_draft(candidate: dict[str, object]) -> None:
    forbidden_keys = sorted(
        {key for key in _walk_keys(candidate) if key in FORBIDDEN_GENERATOR_KEYS}
    )
    assert forbidden_keys == [], (
        "workload_fit_init must stay a draft contract helper, not an app "
        f"scaffolder or deployment generator: {forbidden_keys}"
    )


def test_workload_fit_init_generates_valid_internal_service_candidate() -> None:
    candidate = build_candidate(
        name="payments_gateway",
        kind="service",
        operational_class="internal-service",
        owner="payments-platform",
    )

    assert candidate["name"] == "payments_gateway"
    assert candidate["runtime"] == {"supported": ["local-compose"], "admitted": []}
    assert candidate["operational"]["class"] == "internal-service"
    assert candidate["image"]["repository"] == "payments-gateway"
    _assert_candidate_is_boundary_draft(candidate)
    assert {result.status for result in evaluate_candidate(candidate)} == {"ok"}


def test_workload_fit_init_generates_valid_operator_job_candidate() -> None:
    candidate = build_candidate(
        name="reconcile_external_orders",
        kind="job",
        operational_class="operator-job",
        owner="payments-platform",
    )

    assert candidate["operational"]["trigger"] == "manual"
    assert candidate["job"]["idempotency"] == "<idempotency-mode>"
    _assert_candidate_is_boundary_draft(candidate)
    assert {result.status for result in evaluate_candidate(candidate)} == {"ok"}


def test_workload_fit_init_cli_writes_candidate(tmp_path: Path) -> None:
    output_path = tmp_path / "candidate.json"

    subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_fit_init.py",
            "--name",
            "payments_gateway",
            "--kind",
            "service",
            "--class",
            "internal-service",
            "--owner",
            "payments-platform",
            "--output",
            str(output_path),
        ],
        check=True,
        cwd=ROOT,
    )

    candidate = json.loads(output_path.read_text(encoding="utf-8"))
    assert sorted(tmp_path.iterdir()) == [output_path]
    assert candidate["name"] == "payments_gateway"
    _assert_candidate_is_boundary_draft(candidate)
    assert {result.status for result in evaluate_candidate(candidate)} == {"ok"}
