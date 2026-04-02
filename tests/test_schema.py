"""
test_schema.py — Schema correctness tests.

Asserts the expected tables, columns, and constraints are present on the live DB.
These run at every migration phase — they describe the invariants that must hold
throughout the entire lifecycle, not just at one point in time.
"""

import pytest
from sqlalchemy import inspect, text

# Columns that must survive the full migration sequence unchanged.
_ORDERS_STABLE_COLUMNS = {"id", "customer_id", "total_amount", "status", "submitted_at", "created_at"}

# order_contact_email must exist from the expand phase onward.
_CONTACT_TABLE_COLUMNS = {"order_id", "billing_email", "source", "updated_at"}


def test_orders_stable_columns_present(db_engine):
    """orders table retains all bootstrap-era columns throughout the migration."""
    cols = {c["name"] for c in inspect(db_engine).get_columns("orders")}
    assert not (_ORDERS_STABLE_COLUMNS - cols), f"missing columns: {_ORDERS_STABLE_COLUMNS - cols}"


@pytest.mark.require_phase("dual", "switch", "new_pre_contract", "post_contract")
def test_order_contact_email_table_exists_with_expected_columns(db_engine):
    """order_contact_email exists with all expected columns from the expand phase onward."""
    cols = {c["name"] for c in inspect(db_engine).get_columns("order_contact_email")}
    assert not (_CONTACT_TABLE_COLUMNS - cols), f"missing columns: {_CONTACT_TABLE_COLUMNS - cols}"


@pytest.mark.require_phase("dual", "switch", "new_pre_contract", "post_contract")
def test_order_contact_email_has_primary_key_on_order_id(db_engine):
    """order_contact_email.order_id is the primary key."""
    pk = inspect(db_engine).get_pk_constraint("order_contact_email")
    assert "order_id" in pk["constrained_columns"]


def test_app_runtime_config_table_exists(db_engine):
    """app_runtime_config table exists and contains at least WRITE_MODE and READ_MODE rows."""
    with db_engine.connect() as conn:
        keys = {
            row[0] for row in conn.execute(
                text("SELECT key FROM app_runtime_config WHERE key IN ('WRITE_MODE', 'READ_MODE')")
            ).fetchall()
        }
    assert keys == {"WRITE_MODE", "READ_MODE"}


@pytest.mark.require_phase("post_contract")
def test_billing_email_column_dropped_after_contract(db_engine):
    """orders.billing_email is absent after the contract phase completes."""
    cols = {c["name"] for c in inspect(db_engine).get_columns("orders")}
    assert "billing_email" not in cols
