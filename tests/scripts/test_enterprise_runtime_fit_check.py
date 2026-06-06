from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.platform.enterprise_runtime_fit_check import ENTERPRISE_RUNTIME
from scripts.platform.enterprise_runtime_fit_check import enterprise_fit_rows


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_CAPABILITIES = {
    "authz_policy",
    "ci_cd_delivery",
    "edge_auth",
    "network_connectivity",
    "observability_routing",
}
EXPECTED_PROMOTION_GATE = {
    "owner",
    "config_surface",
    "conformance_test",
    "evidence_artifact",
    "failure_mode",
    "runbook",
}


def test_enterprise_runtime_fit_lists_candidate_only_capabilities() -> None:
    rows = enterprise_fit_rows()

    assert {row.capability for row in rows} == EXPECTED_CAPABILITIES
    assert {row.runtime_target for row in rows} == {ENTERPRISE_RUNTIME}
    assert {row.status for row in rows} == {"candidate-only"}
    assert {row.candidate_only for row in rows} == {True}


def test_enterprise_runtime_fit_exposes_promotion_gate_and_missing_conformance() -> (
    None
):
    rows = enterprise_fit_rows()

    for row in rows:
        assert {item.name for item in row.promotion_gate} == EXPECTED_PROMOTION_GATE
        assert {item.status for item in row.promotion_gate} == {"missing"}
        assert row.required_evidence
        assert row.owned_seams
        assert row.missing_conformance_checks == [
            f"tests/runtime enterprise {row.capability} check",
            f"tests/contracts enterprise {row.capability} contract",
            f"operator evidence fixture for {row.capability}",
        ]


def test_enterprise_runtime_fit_cli_outputs_json() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/enterprise_runtime_fit_check.py",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    rows = json.loads(completed.stdout)

    assert rows[0]["runtime_target"] == ENTERPRISE_RUNTIME
    assert rows[0]["status"] == "candidate-only"
    assert rows[0]["promotion_gate"][0]["name"] == "owner"
