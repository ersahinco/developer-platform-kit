"""Runtime mode behavior across write/read migration phases."""

import pytest
from sqlalchemy import text

from tests.conftest import contact_row, post_order


def _set_read_mode(http_client, mode: str) -> None:
    resp = http_client.post("/admin/read-mode", json={"mode": mode})
    assert resp.status_code == 200, resp.text


@pytest.mark.require_phase("legacy")
def test_legacy_write_no_contact_row(http_client, db_session):
    assert contact_row(db_session, post_order(http_client)) is None


@pytest.mark.require_phase("dual", "switch")
def test_dual_write_persists_to_new_table(http_client, db_session):
    order_id = post_order(http_client, billing_email="dual@example.com")
    row = contact_row(db_session, order_id)
    assert row is not None and row[0] == "dual@example.com"


@pytest.mark.require_phase("new_pre_contract")
def test_new_write_no_legacy_email(http_client, db_session):
    order_id = post_order(http_client, billing_email="new@example.com")
    row = db_session.execute(
        text("SELECT billing_email FROM orders WHERE id=:oid"), {"oid": order_id}
    ).fetchone()
    assert row[0] is None


@pytest.mark.require_phase("dual", "switch", "new_pre_contract", "post_contract")
def test_no_email_no_contact_row(http_client, db_session):
    assert contact_row(db_session, post_order(http_client, billing_email=None)) is None


@pytest.mark.require_phase("legacy", "dual")
def test_read_mode_legacy_uses_orders_column_not_contact_table(
    http_client, committed_db_session
):
    conn = committed_db_session.connection()
    row = conn.execute(
        text("SELECT value FROM app_runtime_config WHERE key='READ_MODE'")
    ).fetchone()
    original_read_mode = row[0] if row else "legacy"

    try:
        _set_read_mode(http_client, "legacy")
        order_id = post_order(http_client, billing_email="legacy@example.com")
        conn.execute(
            text("DELETE FROM order_contact_email WHERE order_id=:oid"),
            {"oid": order_id},
        )
        conn.commit()

        assert (
            http_client.get(f"/orders/{order_id}").json()["billing_email"]
            == "legacy@example.com"
        )
    finally:
        _set_read_mode(http_client, original_read_mode)
