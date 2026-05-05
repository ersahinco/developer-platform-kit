"""
test_schema.py — Schema correctness tests.

Asserts the expected tables, columns, and constraints are present on the live DB.
These run at every migration phase — they describe the invariants that must hold
throughout the entire lifecycle, not just at one point in time.
"""

import pytest
from sqlalchemy import inspect, text

# Columns that must survive the full migration sequence unchanged.
_ORDERS_STABLE_COLUMNS = {
    "id",
    "customer_id",
    "total_amount",
    "status",
    "submitted_at",
    "created_at",
}

# order_contact_email must exist from the expand phase onward.
_CONTACT_TABLE_COLUMNS = {"order_id", "billing_email", "source", "updated_at"}

_OUTBOX_TABLE_COLUMNS = {
    "id",
    "event_type",
    "event_id",
    "aggregate_type",
    "aggregate_id",
    "message_group_id",
    "message_deduplication_id",
    "payload",
    "status",
    "attempt_count",
    "next_attempt_at",
    "locked_until",
    "published_at",
    "last_error",
    "created_at",
    "updated_at",
}

_IDEMPOTENCY_TABLE_COLUMNS = {
    "key",
    "request_hash",
    "status",
    "response_status_code",
    "response_payload",
    "processing_expires_at",
    "last_error",
    "created_at",
    "updated_at",
}

_ORDER_EVENT_RECEIPT_TABLE_COLUMNS = {
    "event_id",
    "event_type",
    "aggregate_type",
    "aggregate_id",
    "idempotency_key",
    "occurred_at",
    "payload",
    "status",
    "duplicate_count",
    "first_seen_at",
    "last_seen_at",
}


def test_orders_stable_columns_present(db_engine):
    """orders table retains all bootstrap-era columns throughout the migration."""
    cols = {c["name"] for c in inspect(db_engine).get_columns("orders")}
    missing = _ORDERS_STABLE_COLUMNS - cols
    assert not missing, f"missing columns: {missing}"


@pytest.mark.require_phase("dual", "switch", "new_pre_contract", "post_contract")
def test_order_contact_email_table_exists_with_expected_columns(db_engine):
    """order_contact_email exists with all expected columns from the expand phase onward."""
    cols = {c["name"] for c in inspect(db_engine).get_columns("order_contact_email")}
    missing = _CONTACT_TABLE_COLUMNS - cols
    assert not missing, f"missing columns: {missing}"


@pytest.mark.require_phase("dual", "switch", "new_pre_contract", "post_contract")
def test_order_contact_email_has_primary_key_on_order_id(db_engine):
    """order_contact_email.order_id is the primary key."""
    pk = inspect(db_engine).get_pk_constraint("order_contact_email")
    assert "order_id" in pk["constrained_columns"]


def test_app_runtime_config_table_exists(db_engine):
    """app_runtime_config table exists and contains at least WRITE_MODE and READ_MODE rows."""
    with db_engine.connect() as conn:
        keys = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT key FROM app_runtime_config WHERE key IN ('WRITE_MODE', 'READ_MODE')"
                )
            ).fetchall()
        }
    assert keys == {"WRITE_MODE", "READ_MODE"}


def test_orders_have_domain_check_constraints(db_engine):
    """orders keeps DB-level guards for the same invariants enforced by the API."""
    constraints = {
        c["name"] for c in inspect(db_engine).get_check_constraints("orders")
    }
    assert "chk_orders_status_known" in constraints
    assert "chk_orders_total_amount_positive" in constraints


def test_outbox_messages_table_exists_with_expected_contract(db_engine):
    """outbox_messages keeps the durable handoff from DB commit to SQS publish."""
    inspector = inspect(db_engine)
    cols = {c["name"] for c in inspector.get_columns("outbox_messages")}
    missing = _OUTBOX_TABLE_COLUMNS - cols
    assert not missing, f"missing columns: {missing}"

    unique_constraints = {
        c["name"] for c in inspector.get_unique_constraints("outbox_messages")
    }
    check_constraints = {
        c["name"] for c in inspector.get_check_constraints("outbox_messages")
    }
    assert "uq_outbox_messages_event_id" in unique_constraints
    assert "chk_outbox_messages_status_known" in check_constraints
    assert "chk_outbox_messages_attempt_count_non_negative" in check_constraints


def test_idempotency_keys_table_exists_with_expected_contract(db_engine):
    """idempotency_keys stores replayable POST responses and in-flight state."""
    inspector = inspect(db_engine)
    cols = {c["name"] for c in inspector.get_columns("idempotency_keys")}
    missing = _IDEMPOTENCY_TABLE_COLUMNS - cols
    assert not missing, f"missing columns: {missing}"

    check_constraints = {
        c["name"] for c in inspector.get_check_constraints("idempotency_keys")
    }
    assert "chk_idempotency_keys_status_known" in check_constraints
    assert "chk_idempotency_keys_completed_has_response" in check_constraints


def test_order_event_receipts_table_exists_with_expected_contract(db_engine):
    """order_event_receipts records consumed async events and duplicate counts."""
    inspector = inspect(db_engine)
    cols = {c["name"] for c in inspector.get_columns("order_event_receipts")}
    missing = _ORDER_EVENT_RECEIPT_TABLE_COLUMNS - cols
    assert not missing, f"missing columns: {missing}"

    check_constraints = {
        c["name"] for c in inspector.get_check_constraints("order_event_receipts")
    }
    assert "chk_order_event_receipts_status_known" in check_constraints
    assert "chk_order_event_receipts_duplicate_count_non_negative" in check_constraints


@pytest.mark.require_phase("post_contract")
def test_billing_email_column_dropped_after_contract(db_engine):
    """orders.billing_email is absent after the contract phase completes."""
    cols = {c["name"] for c in inspect(db_engine).get_columns("orders")}
    assert "billing_email" not in cols
