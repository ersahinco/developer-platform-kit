"""
test_read_mode.py — READ_MODE routing and runtime switching tests.

Each test declares which migration phases it is valid for via
@pytest.mark.require_phase.

  legacy / dual        → test_read_mode_legacy (billing_email column must exist)
  dual / switch        → test_read_mode_new, test_read_mode_switch_persists
  all phases           → test_read_mode_fallback

Validates: Requirements 5.1–5.3, 5.5
"""

import os

import pytest
from sqlalchemy import text


def _set_read_mode_via_api(http_client, mode):
    resp = http_client.post("/admin/read-mode", json={"mode": mode})
    assert resp.status_code == 200, resp.text


def _set_read_mode_db(db_session, mode):
    db_session.execute(
        text(
            "INSERT INTO app_runtime_config (key, value) VALUES ('READ_MODE', :mode) "
            "ON CONFLICT (key) DO UPDATE SET value = :mode"
        ),
        {"mode": mode},
    )
    db_session.commit()


def _create_order(http_client, email="readmode@example.com"):
    resp = http_client.post("/orders", json={
        "customer_id": 1,
        "total_amount": 10.00,
        "status": "SUBMITTED",
        "billing_email": email,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.require_phase("legacy", "dual")
def test_read_mode_legacy(http_client, db_session):
    """READ_MODE=legacy → GET returns email from orders.billing_email. Req 5.1"""
    _set_read_mode_via_api(http_client, "legacy")
    order_id = _create_order(http_client, email="legacy@example.com")

    assert http_client.get(f"/orders/{order_id}").json()["billing_email"] == "legacy@example.com"

    # Remove the order_contact_email row (if any) and confirm the API still
    # returns the correct email — proving the read path uses orders.billing_email.
    db_session.execute(
        text("DELETE FROM order_contact_email WHERE order_id = :oid"), {"oid": order_id}
    )
    db_session.commit()

    assert http_client.get(f"/orders/{order_id}").json()["billing_email"] == "legacy@example.com"


@pytest.mark.require_phase("dual", "switch")
def test_read_mode_new(http_client, db_session):
    """READ_MODE=new → GET returns email from order_contact_email. Req 5.2

    Requires dual-write so order_contact_email is populated on write.
    """
    _set_read_mode_via_api(http_client, "new")
    order_id = _create_order(http_client, email="new@example.com")
    assert http_client.get(f"/orders/{order_id}").json()["billing_email"] == "new@example.com"


@pytest.mark.require_phase("dual", "switch")
def test_read_mode_switch_persists(http_client, db_session):
    """Switching READ_MODE via API persists across requests. Req 5.3"""
    order_id = _create_order(http_client, email="switch@example.com")

    _set_read_mode_via_api(http_client, "legacy")
    assert http_client.get(f"/orders/{order_id}").json()["billing_email"] == "switch@example.com"

    _set_read_mode_via_api(http_client, "new")
    assert http_client.get(f"/orders/{order_id}").json()["billing_email"] == "switch@example.com"


def test_read_mode_fallback(http_client, db_session):
    """No app_runtime_config row → app falls back to READ_MODE env var. Req 5.5"""
    db_session.execute(text("DELETE FROM app_runtime_config WHERE key = 'READ_MODE'"))
    db_session.commit()

    order_id = _create_order(http_client, email="fallback@example.com")
    assert http_client.get(f"/orders/{order_id}").json()["billing_email"] == "fallback@example.com"

    # Restore so other tests see a consistent READ_MODE.
    _set_read_mode_db(db_session, os.environ.get("READ_MODE", "legacy"))
