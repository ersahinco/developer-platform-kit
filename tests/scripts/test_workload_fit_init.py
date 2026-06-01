from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.platform.workload_fit_check import evaluate_candidate
from scripts.platform.workload_fit_init import build_candidate


ROOT = Path(__file__).resolve().parents[2]


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
    assert candidate["name"] == "payments_gateway"
    assert {result.status for result in evaluate_candidate(candidate)} == {"ok"}
