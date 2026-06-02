from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from support_triage_llm import main as support_main
from support_triage_llm.main import app


ROOT = Path(__file__).resolve().parents[3]


def _prompt_path() -> str:
    return str(
        ROOT / "apps" / "support_triage_llm" / "prompts" / "support_triage_v1.md"
    )


def _eval_cases_path() -> str:
    return str(
        ROOT / "apps" / "support_triage_llm" / "sample_data" / "evaluation_cases.json"
    )


def test_health_ready_triage_metrics_and_evidence(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        support_main.settings, "support_triage_prompt_path", _prompt_path()
    )
    monkeypatch.setattr(
        support_main.settings,
        "support_triage_eval_cases_path",
        _eval_cases_path(),
    )
    monkeypatch.setattr(
        support_main.settings, "support_triage_output_dir", str(tmp_path)
    )

    with TestClient(app) as client:
        health = client.get("/health")
        ready = client.get("/ready")
        triage = client.post(
            "/triage",
            json={
                "ticket_id": "T-test",
                "subject": "Production API is down",
                "body": "Checkout is unavailable and customers cannot pay.",
                "customer_tier": "enterprise",
                "run_id": "triage-run",
            },
        )
        metrics = client.get("/metrics")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["checks"]["prompt"] == "ok"
    assert ready.json()["prompt_version"] == "support-triage-v1"
    assert triage.status_code == 200
    payload = triage.json()
    assert payload["status"] == "succeeded"
    assert payload["run_id"] == "triage-run"
    assert payload["prompt_version"] == "support-triage-v1"
    assert payload["category"] == "incident"
    assert payload["priority"] == "urgent"
    assert payload["token_evidence"]["input_tokens"] > 0
    assert payload["estimated_cost_usd"] > 0
    assert metrics.status_code == 200
    assert "support_triage_llm_requests_total" in metrics.text
    assert "support_triage_llm_tokens_total" in metrics.text
    assert "support_triage_llm_cost_usd_total" in metrics.text

    evidence_path = tmp_path / payload["evidence_path"]
    assert evidence_path.is_file()
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["run_id"] == "triage-run"
    assert evidence["evidence_path"] == payload["evidence_path"]
    assert '"event": "support_triage_completed"' in capsys.readouterr().out


def test_evaluate_writes_evaluation_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        support_main.settings, "support_triage_prompt_path", _prompt_path()
    )
    monkeypatch.setattr(
        support_main.settings,
        "support_triage_eval_cases_path",
        _eval_cases_path(),
    )
    monkeypatch.setattr(
        support_main.settings, "support_triage_output_dir", str(tmp_path)
    )

    with TestClient(app) as client:
        response = client.post("/evaluate", json={"run_id": "eval-run"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["event"] == "support_triage_evaluation_completed"
    assert payload["status"] == "succeeded"
    assert payload["case_count"] == 3
    assert payload["passed_count"] == 3
    assert payload["failed_count"] == 0
    evidence = json.loads((tmp_path / payload["evidence_path"]).read_text())
    assert evidence["run_id"] == "eval-run"
    assert evidence["evidence_path"] == payload["evidence_path"]


def test_failed_prompt_load_writes_operator_payload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        support_main.settings,
        "support_triage_prompt_path",
        str(tmp_path / "missing.md"),
    )
    monkeypatch.setattr(
        support_main.settings,
        "support_triage_eval_cases_path",
        _eval_cases_path(),
    )
    monkeypatch.setattr(
        support_main.settings, "support_triage_output_dir", str(tmp_path)
    )

    with TestClient(app) as client:
        ready = client.get("/ready")
        response = client.post(
            "/triage",
            json={
                "ticket_id": "T-fail",
                "subject": "Cannot login",
                "body": "SSO login fails.",
                "run_id": "failed-run",
            },
        )

    assert ready.status_code == 503
    assert response.status_code == 503
    payload = response.json()
    assert payload["event"] == "support_triage_failed"
    assert payload["status"] == "failed"
    assert payload["mode"] == "operator_payload"
    assert payload["run_id"] == "failed-run"
    evidence = json.loads((tmp_path / payload["evidence_path"]).read_text())
    assert evidence["evidence_path"] == payload["evidence_path"]
