from __future__ import annotations

from fastapi.testclient import TestClient

from churn_prediction_api import main as churn_main
from churn_prediction_api.main import app


def test_health_ready_metrics_and_predict(capsys) -> None:
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
    assert health.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["checks"]["model"] == "ok"
    assert ready.json()["model_version"] == "sample-v1"
    assert prediction.status_code == 200
    body = prediction.json()
    assert body["status"] == "succeeded"
    assert body["model_version"] == "sample-v1"
    assert body["run_id"] == "sample-model"
    assert 0 <= body["churn_probability"] <= 1
    assert metrics.status_code == 200
    assert "churn_prediction_requests_total" in metrics.text
    assert "churn_prediction_latency_seconds" in metrics.text

    logs = capsys.readouterr().out
    assert '"event": "churn_prediction"' in logs
    assert '"model_version": "sample-v1"' in logs
    assert '"run_id": "sample-model"' in logs


def test_ready_reports_model_load_failure(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        churn_main.settings, "churn_model_path", str(tmp_path / "missing.json")
    )

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert "model" in response.json()["checks"]


def test_score_churn_uses_model_weights() -> None:
    model = churn_main.load_model(churn_main.Path(churn_main.settings.churn_model_path))
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
