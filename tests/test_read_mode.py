"""test_read_mode.py — READ_MODE edge-case tests."""

import pytest
from sqlalchemy import text

from conftest import post_order


def _set_read_mode(http_client, mode):
    resp = http_client.post("/admin/read-mode", json={"mode": mode})
    assert resp.status_code == 200, resp.text


@pytest.mark.require_phase("legacy", "dual")
def test_read_mode_legacy_uses_orders_column_not_contact_table(http_client, committed_db_session):
    """READ_MODE=legacy serves billing_email from orders.billing_email even when the contact row is absent."""
    conn = committed_db_session.connection()
    row = conn.execute(text("SELECT value FROM app_runtime_config WHERE key='READ_MODE'")).fetchone()
    original_read_mode = row[0] if row else "legacy"

    try:
        _set_read_mode(http_client, "legacy")
        order_id = post_order(http_client, billing_email="legacy@example.com")
        conn.execute(text("DELETE FROM order_contact_email WHERE order_id=:oid"), {"oid": order_id})
        conn.commit()

        assert http_client.get(f"/orders/{order_id}").json()["billing_email"] == "legacy@example.com"
    finally:
        # Restore the original mode so subsequent tests see a consistent app state.
        _set_read_mode(http_client, original_read_mode)
