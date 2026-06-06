from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.platform.capability_proof import ACTIVE_CAPABILITY_AREAS
from scripts.platform.capability_proof import capability_proofs


ROOT = Path(__file__).resolve().parents[2]


def test_local_capability_proof_covers_required_runtime_areas() -> None:
    rows = capability_proofs("local-compose")

    assert [row.area for row in rows] == list(ACTIVE_CAPABILITY_AREAS)
    assert {row.status for row in rows} == {"ok"}
    assert {row.capability for row in rows} == set(ACTIVE_CAPABILITY_AREAS.values())


def test_cloud_capability_proof_covers_required_runtime_areas() -> None:
    rows = capability_proofs("aws-ecs")

    assert [row.area for row in rows] == list(ACTIVE_CAPABILITY_AREAS)
    assert {row.status for row in rows} == {"ok"}
    assert {row.capability for row in rows} == set(ACTIVE_CAPABILITY_AREAS.values())


def test_capability_proof_cli_outputs_json() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/capability_proof.py",
            "--runtime-target",
            "local-compose",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    rows = json.loads(completed.stdout)

    assert rows[0]["runtime_target"] == "local-compose"
    assert rows[0]["area"] == "authn"
    assert rows[0]["capability"] == "edge_auth"
    assert rows[0]["status"] == "ok"


def test_capability_proof_auth_checks_include_structured_auth_evidence() -> None:
    rows = {row.area: row for row in capability_proofs("aws-ecs")}
    auth_checks = {check.name: check for check in rows["authn"].checks}

    assert any("auth_status" in check.evidence for check in auth_checks.values())
    assert any('"denied"' in check.evidence for check in auth_checks.values())
