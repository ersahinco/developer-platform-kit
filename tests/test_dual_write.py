"""
test_dual_write.py — WRITE_MODE routing tests.

Each test declares which migration phases it is valid for via
@pytest.mark.require_phase. Tests are skipped automatically outside those phases.

  legacy           → test_legacy_write_no_contact_row
  dual / switch    → test_dual_write_persists_to_new_table
  new_pre_contract → test_new_write_no_legacy_email
  dual / switch / new_pre_contract / post_contract → test_no_email_no_contact_row

Validates: Requirements 4.1–4.4, 10.2, 10.3
"""

import pytest
from sqlalchemy import text


_ORDER_PAYLOAD = {
    "customer_id": 1,
    "total_amount": 42.00,
    "status": "SUBMITTED",
    "billing_email": "dual@example.com",
}

_ORDER_PAYLOAD_NO_EMAIL = {
    "customer_id": 1,
    "total_amount": 10.00,
    "status": "SUBMITTED",
}


def _post_order(http_client, payload=None):
    resp = http_client.post("/orders", json=payload or _ORDER_PAYLOAD)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _contact_row(db_session, order_id):
    return db_session.execute(
        text("SELECT billing_email FROM order_contact_email WHERE order_id = :oid"),
        {"oid": order_id},
    ).fetchone()


@pytest.mark.require_phase("legacy")
def test_legacy_write_no_contact_row(http_client, db_session):
    """WRITE_MODE=legacy — no row written to order_contact_email. Req 4.2"""
    order_id = _post_order(http_client)
    assert _contact_row(db_session, order_id) is None


@pytest.mark.require_phase("dual", "switch")
def test_dual_write_persists_to_new_table(http_client, db_session):
    """WRITE_MODE=dual — row upserted into order_contact_email. Req 4.1"""
    order_id = _post_order(http_client)
    contact = _contact_row(db_session, order_id)
    assert contact is not None
    assert contact[0] == _ORDER_PAYLOAD["billing_email"]


@pytest.mark.require_phase("new_pre_contract")
def test_new_write_no_legacy_email(http_client, db_session):
    """WRITE_MODE=new (pre-Contract) — orders.billing_email is NULL. Req 4.3

    The column still exists but the app must not write to it.
    """
    order_id = _post_order(http_client)
    row = db_session.execute(
        text("SELECT billing_email FROM orders WHERE id = :oid"), {"oid": order_id}
    ).fetchone()
    assert row is not None
    assert row[0] is None, "orders.billing_email must be NULL when WRITE_MODE=new"


@pytest.mark.require_phase("dual", "switch", "new_pre_contract", "post_contract")
def test_no_email_no_contact_row(http_client, db_session):
    """No billing_email in request — no row in order_contact_email. Req 4.4

    Only meaningful when the app would otherwise write to order_contact_email
    (dual / switch / new modes). Skipped in legacy mode where the table is
    never written and the assertion would be vacuously true.
    """
    order_id = _post_order(http_client, payload=_ORDER_PAYLOAD_NO_EMAIL)
    assert _contact_row(db_session, order_id) is None
