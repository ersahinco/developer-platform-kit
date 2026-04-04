"""test_api.py — HTTP layer integration tests."""

import pytest

from conftest import contact_row, post_order


def test_create_and_read_order_returns_billing_email(http_client):
    """POST /orders then GET /orders/{id} returns the same billing_email."""
    order_id = post_order(http_client, billing_email="test@example.com")
    resp = http_client.get(f"/orders/{order_id}")
    assert resp.status_code == 200
    assert resp.json()["billing_email"] == "test@example.com"


def test_create_order_without_email_returns_null(http_client):
    """Orders with no billing_email are created successfully; GET returns null."""
    order_id = post_order(http_client, billing_email=None)
    assert http_client.get(f"/orders/{order_id}").json()["billing_email"] is None


def test_order_not_found_returns_404(http_client):
    """GET /orders/{id} for a non-existent order returns 404."""
    assert http_client.get("/orders/999999999").status_code == 404


@pytest.mark.parametrize("status", ["SUBMITTED", "PAID", "CANCELLED"])
def test_valid_order_statuses_are_accepted(http_client, status):
    """All valid order statuses are accepted by POST /orders."""
    resp = http_client.post(
        "/orders",
        json={
            "customer_id": 1,
            "total_amount": "10.00",
            "status": status,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == status


def test_invalid_order_status_is_rejected(http_client):
    """POST /orders with an invalid status returns 422."""
    resp = http_client.post(
        "/orders",
        json={
            "customer_id": 1,
            "total_amount": "10.00",
            "status": "PENDING",
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
