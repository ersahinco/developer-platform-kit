"""test_api.py — HTTP layer integration tests."""

import pytest
from sqlalchemy import text

from conftest import contact_row, post_order


def test_create_and_read_order_returns_billing_email(http_client):
    """POST /orders then GET /orders/{id} returns the same billing_email."""
    order_id = post_order(http_client, billing_email="test@example.com")
    resp = http_client.get(f"/orders/{order_id}")
    assert resp.status_code == 200
    assert resp.json()["billing_email"] == "test@example.com"
    assert resp.json()["status"] == "SUBMITTED"


def test_create_order_without_email_returns_null(http_client):
    """Orders with no billing_email are created successfully; GET returns null."""
    order_id = post_order(http_client, billing_email=None)
    assert http_client.get(f"/orders/{order_id}").json()["billing_email"] is None


def test_create_order_records_order_created_outbox_message(http_client, db_session):
    """POST /orders durably records the order.created.v1 handoff."""
    order_id = post_order(http_client, billing_email="test@example.com")
    row = db_session.execute(
        text(
            "SELECT event_type, event_id, message_group_id, "
            "message_deduplication_id, payload, status "
            "FROM outbox_messages WHERE aggregate_type='order' AND aggregate_id=:id"
        ),
        {"id": order_id},
    ).one()

    assert row.event_type == "order.created.v1"
    assert row.event_id == f"order.created.v1:{order_id}"
    assert row.message_group_id == "customer-1"
    assert row.message_deduplication_id == f"order.created.v1:{order_id}"
    assert row.payload["event_id"] == f"order.created.v1:{order_id}"
    assert row.status in {"pending", "processing", "published"}


def test_order_not_found_returns_404(http_client):
    """GET /orders/{id} for a non-existent order returns 404."""
    assert http_client.get("/orders/999999999").status_code == 404


def test_metrics_endpoint_exposes_prometheus_text(http_client):
    """GET /metrics exposes Prometheus-format application metrics."""
    assert http_client.get("/health").status_code == 200
    resp = http_client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    assert "http_requests_total" in resp.text


def test_order_status_is_owned_by_application(http_client):
    """POST /orders rejects caller-supplied status; new orders start as SUBMITTED."""
    resp = http_client.post(
        "/orders",
        json={
            "customer_id": 1,
            "total_amount": "10.00",
            "status": "PAID",
        },
    )
    assert resp.status_code == 422


def test_non_positive_order_amount_is_rejected(http_client):
    """POST /orders requires total_amount greater than zero."""
    resp = http_client.post(
        "/orders",
        json={
            "customer_id": 1,
            "total_amount": "0.00",
        },
    )
    assert resp.status_code == 422


def test_malformed_billing_email_is_rejected(http_client):
    """POST /orders validates the billing_email format before writing."""
    resp = http_client.post(
        "/orders",
        json={
            "customer_id": 1,
            "total_amount": "10.00",
            "billing_email": "not-an-email",
        },
    )
    assert resp.status_code == 422


@pytest.mark.require_phase("dual", "switch", "new_pre_contract")
def test_billing_email_written_to_contact_table(http_client, db_session):
    """POST /orders with billing_email writes a row to order_contact_email."""
    order_id = post_order(http_client, billing_email="contact@example.com")
    row = contact_row(db_session, order_id)
    assert row is not None and row[0] == "contact@example.com"


@pytest.mark.require_phase("dual", "switch", "new_pre_contract")
def test_no_billing_email_leaves_contact_table_empty(http_client, db_session):
    """POST /orders without billing_email writes no row to order_contact_email."""
    order_id = post_order(http_client, billing_email=None)
    assert contact_row(db_session, order_id) is None
