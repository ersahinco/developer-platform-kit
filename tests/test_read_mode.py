"""test_read_mode.py — READ_MODE routing and runtime switching tests. Req 5.1–5.3, 5.5"""

import os

import pytest
from sqlalchemy import text

from conftest import post_order


def _set_read_mode(http_client, mode):
    resp = http_client.post("/admin/read-mode", json={"mode": mode})
    assert resp.status_code == 200, resp.text


def _get_email(http_client, order_id):
    return http_client.get(f"/orders/{order_id}").json()["billing_email"]


@pytest.mark.require_phase("legacy", "dual")
def test_read_mode_legacy(http_client, db_session):
    """READ_MODE=legacy → email served from orders.billing_email. Req 5.1"""
    _set_read_mode(http_client, "legacy")
    order_id = post_order(http_client, billing_email="legacy@example.com")

    # Remove contact row to prove the legacy column is the source.
    db_session.execute(text("DELETE FROM order_contact_email WHERE order_id=:oid"), {"oid": order_id})
    db_session.commit()

    assert _get_email(http_client, order_id) == "legacy@example.com"


@pytest.mark.require_phase("dual", "switch")
def test_read_mode_new(http_client, db_session):
    """READ_MODE=new → email served from order_contact_email. Req 5.2"""
    _set_read_mode(http_client, "new")
    order_id = post_order(http_client, billing_email="new@example.com")
    assert _get_email(http_client, order_id) == "new@example.com"


@pytest.mark.require_phase("dual", "switch")
def test_read_mode_switch_persists(http_client, db_session):
    """Switching READ_MODE via API persists across requests. Req 5.3"""
    order_id = post_order(http_client, billing_email="switch@example.com")
    for mode in ("legacy", "new"):
        _set_read_mode(http_client, mode)
        assert _get_email(http_client, order_id) == "switch@example.com"


@pytest.mark.require_phase("legacy", "dual", "switch")
def test_read_mode_fallback(http_client, committed_db_session):
    """No app_runtime_config row → falls back to READ_MODE env var. Req 5.5"""
    conn = committed_db_session.connection()
    conn.execute(text("DELETE FROM app_runtime_config WHERE key='READ_MODE'"))
    conn.commit()

    order_id = post_order(http_client, billing_email="fallback@example.com")
    assert _get_email(http_client, order_id) == "fallback@example.com"

    # Restore
    conn.execute(
        text("INSERT INTO app_runtime_config (key, value) VALUES ('READ_MODE', :m) "
             "ON CONFLICT (key) DO UPDATE SET value=:m"),
        {"m": os.environ.get("READ_MODE", "legacy")},
    )
    conn.commit()
