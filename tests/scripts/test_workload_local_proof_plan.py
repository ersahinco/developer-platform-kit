from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.platform.workload_local_proof_plan import build_local_proof_plan


ROOT = Path(__file__).resolve().parents[2]
WORKLOAD_FIXTURES = ROOT / "tests" / "fixtures" / "workloads"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _current_workload(name: str) -> dict[str, object]:
    contract = _load_json(ROOT / "platform" / "workloads.json")
    workloads = contract["workloads"]
    assert isinstance(workloads, list)
    return next(workload for workload in workloads if workload["name"] == name)


def test_local_proof_plan_reports_foreign_fixture_ready() -> None:
    candidate = _load_json(WORKLOAD_FIXTURES / "foreign_internal_service_good.json")

    plan = build_local_proof_plan(candidate)

    assert plan.fit is True
    assert plan.local_proof == "ready"
    assert plan.add == []
    assert plan.prove == [
        "/health",
        "/ready",
        "/metrics with workload_info",
        "declared config env/secrets",
        "structured workload logs",
    ]


def test_local_proof_plan_lists_missing_work_for_passing_candidate() -> None:
    candidate = {
        **_load_json(WORKLOAD_FIXTURES / "foreign_internal_service_good.json"),
        "name": "future_inventory_sync",
        "image": {
            "repository": "future-inventory-sync",
            "package": "future-inventory-sync",
            "command": "python -m future_inventory_sync.main",
        },
    }

    plan = build_local_proof_plan(candidate)

    assert plan.fit is True
    assert plan.local_proof == "not ready"
    assert plan.add == [
        "platform/workloads.json entry",
        "apps/future_inventory_sync/config.py",
        "apps/future_inventory_sync/main.py",
        "apps/future_inventory_sync/pyproject.toml",
        "compose service future-inventory-sync",
        "platform/runtime-conformance.json fixture",
    ]
    assert plan.prove == [
        "/health",
        "/ready",
        "/metrics with workload_info",
        "declared config env/secrets",
        "structured workload logs",
    ]


def test_local_proof_plan_reports_existing_workload_ready() -> None:
    plan = build_local_proof_plan(_current_workload("api"))

    assert plan.fit is True
    assert plan.local_proof == "ready"
    assert plan.add == []
    assert "/health" in plan.prove


def test_local_proof_plan_uses_job_proof_items() -> None:
    candidate = {
        "name": "foreign_reconcile_job",
        "kind": "job",
        "use_cases": ["operator-task"],
        "owner": "supply-chain-platform",
        "runtime": {"supported": ["local-compose"], "admitted": []},
        "operational": {"class": "operator-job", "trigger": "manual"},
        "image": {
            "repository": "foreign-reconcile-job",
            "package": "foreign-reconcile-job",
            "command": "python -m foreign_reconcile_job.main",
        },
        "traces": {"supported": False},
        "config": {"env": [], "secrets": []},
        "job": {"idempotency": "run_id"},
    }

    plan = build_local_proof_plan(candidate)

    assert plan.fit is True
    assert plan.local_proof == "not ready"
    assert plan.prove == [
        "process exit status",
        "terminal event",
        "idempotency mode",
        "declared config env/secrets",
    ]


def test_local_proof_plan_blocks_failing_candidate() -> None:
    candidate = _load_json(WORKLOAD_FIXTURES / "foreign_internal_service_bad.json")

    plan = build_local_proof_plan(candidate)

    assert plan.fit is False
    assert plan.local_proof == "blocked"
    assert plan.add == []
    assert plan.prove == []
    assert any("platform_edge_boundary" in item for item in plan.blocked_by)


def test_local_proof_plan_cli_outputs_actionable_text() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_local_proof_plan.py",
            "--candidate",
            str(WORKLOAD_FIXTURES / "foreign_internal_service_good.json"),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert "fit: yes" in completed.stdout
    assert "local proof: ready" in completed.stdout
    assert "- none" in completed.stdout
    assert "- /metrics with workload_info" in completed.stdout


def test_local_proof_plan_cli_outputs_json() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_local_proof_plan.py",
            "--candidate",
            str(WORKLOAD_FIXTURES / "foreign_internal_service_good.json"),
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    plan = json.loads(completed.stdout)
    assert plan["fit"] is True
    assert plan["local_proof"] == "ready"
    assert plan["add"] == []
