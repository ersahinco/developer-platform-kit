from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from churn_prediction_api import main as churn_main
from churn_prediction_api.main import app
from churn_prediction_api.model import load_model


def test_health_ready_metrics_and_prediction_include_model_lineage(capsys) -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        ready = client.get("/ready")
        prediction = client.post(
            "/predict",
            json={
                "customer_id": "C-test",
                "tenure_months": 6,
                "monthly_charges": 112.0,
                "support_tickets_90d": 4,
                "late_payments_12m": 3,
                "usage_drop_pct": 58,
            },
        )
        metrics = client.get("/metrics")

    assert health.status_code == 200
    assert ready.status_code == 200
    assert ready.json()["checks"]["model"] == "promoted"
    assert ready.json()["model_schema_version"] == 1
    assert prediction.status_code == 200
    body = prediction.json()
    assert (
        body["model_version"]
        == load_model(Path(churn_main.settings.churn_model_path))["model_version"]
    )
    assert len(body["training_data_sha256"]) == 64
    assert 0 <= body["churn_probability"] <= 1
    assert metrics.status_code == 200
    assert "churn_prediction_requests_total" in metrics.text
    assert '"event": "churn_prediction"' in capsys.readouterr().out


def test_ready_reports_model_contract_failure(tmp_path: Path, monkeypatch) -> None:
    bad_model = tmp_path / "model.json"
    bad_model.write_text('{"schema_version": 99}', encoding="utf-8")
    monkeypatch.setattr(churn_main.settings, "churn_model_path", str(bad_model))

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert "missing fields" in response.json()["checks"]["model"]


def test_model_loader_rejects_unpromoted_artifact(tmp_path: Path) -> None:
    source = Path(churn_main.settings.churn_model_path)
    model = json.loads(source.read_text(encoding="utf-8"))
    model["promotion"]["decision"] = "reject"
    path = tmp_path / "rejected.json"
    path.write_text(json.dumps(model), encoding="utf-8")

    with pytest.raises(RuntimeError, match="promotion gate"):
        load_model(path)


def test_score_churn_uses_standardized_model_contract() -> None:
    model = load_model(Path(churn_main.settings.churn_model_path))
    low_risk = churn_main.score_churn(
        model=model,
        features={
            "tenure_months": 48,
            "monthly_charges": 60.0,
            "support_tickets_90d": 0,
            "late_payments_12m": 0,
            "usage_drop_pct": 2,
        },
    )
    high_risk = churn_main.score_churn(
        model=model,
        features={
            "tenure_months": 3,
            "monthly_charges": 120.0,
            "support_tickets_90d": 5,
            "late_payments_12m": 4,
            "usage_drop_pct": 65,
        },
    )

    assert high_risk > low_risk
