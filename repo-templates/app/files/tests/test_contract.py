"""The contract the deploy lane and the load balancer depend on."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_workload_identity() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["workload"] == "__WORKLOAD_NAME__"


def test_ready_is_true_once_startup_completed() -> None:
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200


def test_ready_is_false_before_startup() -> None:
    # No lifespan, so startup never ran. The load balancer must see 503.
    assert TestClient(app).get("/ready").status_code == 503


def test_metrics_are_prometheus_text() -> None:
    with TestClient(app) as client:
        response = client.get("/metrics")
    assert response.status_code == 200
    assert "__WORKLOAD_SLUG___requests_total" in response.text
