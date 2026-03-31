"""test_dual_write.py — WRITE_MODE routing tests. Req 4.1–4.4, 10.2, 10.3"""

import pytest
from sqlalchemy import text

from conftest import contact_row, post_order


@pytest.mark.require_phase("legacy")
def test_legacy_write_no_contact_row(http_client, db_session):
    """WRITE_MODE=legacy — no row written to order_contact_email. Req 4.2"""
    assert contact_row(db_session, post_order(http_client)) is None


@pytest.mark.require_phase("dual", "switch")
def test_dual_write_persists_to_new_table(http_client, db_session):
    """WRITE_MODE=dual — row upserted into order_contact_email. Req 4.1"""
    order_id = post_order(http_client, billing_email="dual@example.com")
    row = contact_row(db_session, order_id)
    assert row is not None and row[0] == "dual@example.com"


@pytest.mark.require_phase("new_pre_contract")
def test_new_write_no_legacy_email(http_client, db_session):
    """WRITE_MODE=new — orders.billing_email must be NULL. Req 4.3"""
    order_id = post_order(http_client, billing_email="new@example.com")
    row = db_session.execute(
        text("SELECT billing_email FROM orders WHERE id=:oid"), {"oid": order_id}
    ).fetchone()
    assert row[0] is None


@pytest.mark.require_phase("dual", "switch", "new_pre_contract", "post_contract")
def test_no_email_no_contact_row(http_client, db_session):
    """No billing_email in request — no row in order_contact_email. Req 4.4"""
    assert contact_row(db_session, post_order(http_client, billing_email=None)) is None
