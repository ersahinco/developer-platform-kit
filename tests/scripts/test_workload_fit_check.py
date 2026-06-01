from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.platform.workload_fit_check import evaluate_candidate


ROOT = Path(__file__).resolve().parents[2]
WORKLOAD_FIXTURES = ROOT / "tests" / "fixtures" / "workloads"


def _valid_candidate() -> dict[str, object]:
    return {
        "name": "payments_gateway",
        "kind": "service",
        "use_cases": ["internal-api", "connector"],
        "owner": "payments-platform",
        "runtime": {"supported": ["local-compose"], "admitted": []},
        "operational": {"class": "internal-service", "exposure": "internal"},
        "service": {"port": 8080},
        "image": {
            "repository": "payments-gateway",
            "package": "payments-gateway",
            "command": "python -m payments_gateway.main",
        },
        "metrics": {
            "format": "prometheus",
            "required_names": ["workload_info", "http_requests_total"],
        },
        "traces": {"supported": False},
        "database": {"semantics": "postgresql", "pooling": "direct"},
        "config": {
            "env": ["DATABASE_URL", "DB_HOST", "DB_PORT", "DB_USER", "DB_NAME"],
            "secrets": ["DB_PASSWORD"],
        },
    }


def test_workload_fit_check_accepts_stable_center_candidate() -> None:
    results = evaluate_candidate(_valid_candidate())

    assert {result.status for result in results} == {"ok"}


def test_workload_fit_check_rejects_platform_edge_wiring() -> None:
    candidate = {
        **_valid_candidate(),
        "runtime": {"supported": ["local-compose"], "admitted": ["aws-ecs"]},
        "account_id": "123456789012",
        "dns": {"fqdn": "payments.internal.example.com"},
        "iam": {"role_arn": "arn:aws:iam::123456789012:role/payments-task-role"},
        "ci": {"jenkins": "payments-main"},
        "observability": {"datadog_index": "payments-prod"},
        "database": {
            "semantics": "rds",
            "pooling": "direct",
            "host": "payments-db.cluster-abc.eu-central-1.rds.amazonaws.com",
        },
        "config": {
            "env": ["DATABASE_URL", "DD_SERVICE"],
            "secrets": ["DB_PASSWORD", "SPLUNK_TOKEN"],
        },
    }

    results = evaluate_candidate(candidate)
    failures = {
        result.area: result.message for result in results if result.status == "fail"
    }

    assert "runtime_scope" in failures
    assert "platform_edge_boundary" in failures
    assert "database_intent" in failures
    assert "observability_contract" in failures
    assert "account_id" in failures["platform_edge_boundary"]
    assert "Datadog/Splunk" in failures["platform_edge_boundary"]


def test_workload_fit_check_cli_outputs_json(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(_valid_candidate()), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_fit_check.py",
            "--candidate",
            str(candidate_path),
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    rows = json.loads(completed.stdout)
    assert rows[0]["area"] == "stable_center_fields"
    assert {row["status"] for row in rows} == {"ok"}


def test_workload_fit_check_cli_prints_next_actions_on_success(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(_valid_candidate()), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_fit_check.py",
            "--candidate",
            str(candidate_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert "fit: yes" in completed.stdout
    assert "next make workload-readiness" in completed.stdout
    assert "next make platform-doctor" in completed.stdout
    assert (
        "next add to platform/workloads.json only after local proof exists"
        in completed.stdout
    )


def test_workload_fit_check_cli_groups_removals_on_failure(tmp_path: Path) -> None:
    candidate = {
        **_valid_candidate(),
        "dns": {"fqdn": "payments.internal.example.com"},
        "iam": {"role_arn": "arn:aws:iam::123456789012:role/payments-task-role"},
        "observability": {"datadog_index": "payments-prod"},
    }
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_fit_check.py",
            "--candidate",
            str(candidate_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert completed.returncode == 1
    assert "fit: no" in completed.stdout
    assert "remove from stable center:" in completed.stdout
    assert "- dns.fqdn" in completed.stdout
    assert "- iam.role_arn" in completed.stdout
    assert "- observability.datadog_index" in completed.stdout
    assert "keep as workload contract:" in completed.stdout
    assert "- owner" in completed.stdout
    assert "- use_cases" in completed.stdout
    assert "- database semantics" in completed.stdout


def test_workload_fit_check_rejects_messy_foreign_fixture() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_fit_check.py",
            "--candidate",
            str(WORKLOAD_FIXTURES / "foreign_internal_service_bad.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert completed.returncode == 1
    assert "fit: no" in completed.stdout
    assert "- dns.fqdn" in completed.stdout
    assert "- iam.role_arn" in completed.stdout
    assert "- observability.datadog_index" in completed.stdout
    assert "- terraform.workspace" in completed.stdout


def test_workload_fit_check_accepts_corrected_foreign_fixture() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_fit_check.py",
            "--candidate",
            str(WORKLOAD_FIXTURES / "foreign_internal_service_good.json"),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert "fit: yes" in completed.stdout
    assert "next make workload-readiness" in completed.stdout
