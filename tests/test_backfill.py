"""
test_backfill.py — Backfill worker tests.

Valid phases: legacy, dual, switch, new_pre_contract
(any phase where orders.billing_email still exists — the worker reads from it)

Validates: Requirements 6.2–6.4, 6.7
"""

import json
import os
import subprocess
import sys

import pytest
from sqlalchemy import text

import metrics

JOB_NAME = "order_contact_email_backfill"
WORKER_SRC = os.path.join(os.path.dirname(__file__), "..", "worker", "src")

_PRE_CONTRACT_PHASES = ("legacy", "dual", "switch", "new_pre_contract")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_order(conn, billing_email=None):
    row = conn.execute(
        text(
            "INSERT INTO orders (customer_id, total_amount, status, submitted_at, billing_email) "
            "VALUES (1, 10.00, 'SUBMITTED', NOW(), :billing_email) RETURNING id"
        ),
        {"billing_email": billing_email},
    ).fetchone()
    return row.id


def _reset_checkpoint(conn):
    conn.execute(text("DELETE FROM backfill_progress WHERE job_name = :job"), {"job": JOB_NAME})
    conn.commit()


def _get_checkpoint(conn):
    row = conn.execute(
        text("SELECT last_order_id, rows_processed FROM backfill_progress WHERE job_name = :job"),
        {"job": JOB_NAME},
    ).fetchone()
    return (row.last_order_id, row.rows_processed) if row else (0, 0)


def _contact_email_count(conn):
    return conn.execute(text("SELECT COUNT(*) FROM order_contact_email")).fetchone()[0]


def _run_worker(**extra_env):
    env = {**os.environ, **extra_env}
    return subprocess.run(
        [sys.executable, "backfill.py"],
        cwd=WORKER_SRC,
        env=env,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.require_phase(*_PRE_CONTRACT_PHASES)
def test_batch_selection_predicate(committed_db_session):
    """Rows with billing_email are backfilled; rows without are skipped. Req 6.2"""
    conn = committed_db_session.connection()
    _reset_checkpoint(conn)

    id_a = _insert_order(conn, billing_email="a@example.com")
    id_null = _insert_order(conn, billing_email=None)
    id_b = _insert_order(conn, billing_email="b@example.com")
    conn.commit()

    assert _run_worker().returncode == 0

    committed_db_session.expire_all()
    inserted = {
        r.order_id
        for r in conn.execute(
            text("SELECT order_id FROM order_contact_email WHERE order_id IN :ids"),
            {"ids": (id_a, id_null, id_b)},
        ).fetchall()
    }
    assert id_a in inserted
    assert id_b in inserted
    assert id_null not in inserted


@pytest.mark.require_phase(*_PRE_CONTRACT_PHASES)
def test_backfill_idempotence(committed_db_session):
    """Running the worker twice produces the same row count. Req 6.3"""
    conn = committed_db_session.connection()
    _reset_checkpoint(conn)
    _insert_order(conn, billing_email="idem@example.com")
    conn.commit()

    assert _run_worker().returncode == 0
    committed_db_session.expire_all()
    count_first = _contact_email_count(conn)

    assert _run_worker().returncode == 0
    committed_db_session.expire_all()
    assert _contact_email_count(conn) == count_first


@pytest.mark.require_phase(*_PRE_CONTRACT_PHASES)
def test_checkpoint_update(committed_db_session):
    """Checkpoint advances after a batch. Req 6.4"""
    conn = committed_db_session.connection()
    _reset_checkpoint(conn)
    order_id = _insert_order(conn, billing_email="ckpt@example.com")
    conn.commit()

    before, _ = _get_checkpoint(conn)
    assert _run_worker().returncode == 0
    committed_db_session.expire_all()

    after, processed = _get_checkpoint(conn)
    assert after >= order_id
    assert after > before
    assert processed > 0


@pytest.mark.require_phase(*_PRE_CONTRACT_PHASES)
def test_clean_exit_when_empty(committed_db_session):
    """Worker exits 0 with 'backfill complete' when no rows remain. Req 6.4"""
    conn = committed_db_session.connection()
    _reset_checkpoint(conn)
    _insert_order(conn, billing_email="done@example.com")
    conn.commit()

    first = _run_worker()
    assert first.returncode == 0, first.stderr
    assert "backfill complete" in first.stdout

    second = _run_worker()
    assert second.returncode == 0, second.stderr
    assert "backfill complete" in second.stdout


def test_log_batch_fields():
    """log_batch emits a JSON line with last_order_id, inserted, elapsed_ms. Req 6.7"""
    import io
    buf = io.StringIO()
    old, sys.stdout = sys.stdout, buf
    try:
        metrics.log_batch(42, 100, 12.5)
    finally:
        sys.stdout = old

    data = json.loads(buf.getvalue().strip())
    assert data["last_order_id"] == 42
    assert data["inserted"] == 100
    assert data["elapsed_ms"] == 12.5
