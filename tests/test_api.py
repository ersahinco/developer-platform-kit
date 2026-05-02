"""test_api.py — HTTP layer integration tests."""

from concurrent.futures import ThreadPoolExecutor
import uuid

import httpx
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
    assert row.status == "pending"


def test_create_order_replays_same_response_for_idempotency_key(
    http_client, db_session
):
    """POST /orders with the same Idempotency-Key replays the original response."""
    payload = {
        "customer_id": 1,
        "total_amount": "10.00",
        "billing_email": "idem@example.com",
    }
    headers = {"Idempotency-Key": f"test-create-order-replay-{uuid.uuid4().hex}"}

    first = http_client.post("/orders", json=payload, headers=headers)
    second = http_client.post("/orders", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json() == first.json()

    order_id = first.json()["id"]
    outbox_count = db_session.execute(
        text(
            "SELECT COUNT(*) FROM outbox_messages "
            "WHERE aggregate_type='order' AND aggregate_id=:id"
        ),
        {"id": order_id},
    ).scalar_one()
    assert outbox_count == 1


def test_create_order_idempotency_key_rejects_different_request(http_client):
    """Reusing a key with a different request body returns 409."""
    headers = {"Idempotency-Key": f"test-create-order-conflict-{uuid.uuid4().hex}"}
    first = http_client.post(
        "/orders",
        json={"customer_id": 1, "total_amount": "10.00"},
        headers=headers,
    )
    second = http_client.post(
        "/orders",
        json={"customer_id": 1, "total_amount": "11.00"},
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_create_order_without_idempotency_key_still_creates_each_request(http_client):
    """Clients that do not send Idempotency-Key keep the original create semantics."""
    first = post_order(http_client, billing_email="no-key-a@example.com")
    second = post_order(http_client, billing_email="no-key-b@example.com")

    assert first != second


def test_concurrent_same_key_requests_create_one_order(base_url, db_session):
    """Concurrent same-key retries serialize to one persisted order."""
    payload = {
        "customer_id": 1,
        "total_amount": "10.00",
        "billing_email": "concurrent-idem@example.com",
    }
    headers = {"Idempotency-Key": f"test-concurrent-create-order-{uuid.uuid4().hex}"}

    def submit() -> httpx.Response:
        with httpx.Client(base_url=base_url, timeout=30.0) as client:
            return client.post("/orders", json=payload, headers=headers)

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: submit(), range(2)))

    assert [r.status_code for r in responses] == [201, 201]
    order_ids = {r.json()["id"] for r in responses}
    assert len(order_ids) == 1
    order_id = order_ids.pop()

    outbox_count = db_session.execute(
        text(
            "SELECT COUNT(*) FROM outbox_messages "
            "WHERE aggregate_type='order' AND aggregate_id=:id"
        ),
        {"id": order_id},
    ).scalar_one()
    assert outbox_count == 1


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
