"""test_backfill.py — Backfill worker tests. Req 6.2–6.4, 6.7"""

import io
import json
import os
import subprocess
import sys

import pytest
from sqlalchemy import text

import metrics

_PHASES = ("legacy", "dual", "switch", "new_pre_contract")
_WORKER_SRC = os.path.join(os.path.dirname(__file__), "..", "worker", "src")
_JOB = "order_contact_email_backfill"


def _run_worker(**env):
    return subprocess.run(
        [sys.executable, "backfill.py"],
        cwd=_WORKER_SRC,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
    )


def _insert_order(conn, billing_email=None):
    return conn.execute(
        text("INSERT INTO orders (customer_id, total_amount, status, submitted_at, billing_email) "
             "VALUES (1, 10.00, 'SUBMITTED', NOW(), :e) RETURNING id"),
        {"e": billing_email},
    ).fetchone().id


def _reset_checkpoint(conn):
    conn.execute(text("DELETE FROM backfill_progress WHERE job_name=:j"), {"j": _JOB})
    conn.commit()


@pytest.mark.require_phase(*_PHASES)
def test_batch_selection_predicate(committed_db_session):
    """Rows with billing_email are backfilled; NULL rows are skipped. Req 6.2"""
    conn = committed_db_session.connection()
    _reset_checkpoint(conn)
    id_a = _insert_order(conn, "a@example.com")
    id_null = _insert_order(conn, None)
    id_b = _insert_order(conn, "b@example.com")
    conn.commit()

    assert _run_worker().returncode == 0
    committed_db_session.expire_all()

    inserted = {
        r.order_id for r in conn.execute(
            text("SELECT order_id FROM order_contact_email WHERE order_id IN :ids"),
            {"ids": (id_a, id_null, id_b)},
        ).fetchall()
    }
    assert inserted == {id_a, id_b}


@pytest.mark.require_phase(*_PHASES)
def test_backfill_idempotence(committed_db_session):
    """Running the worker twice produces the same row count. Req 6.3"""
    conn = committed_db_session.connection()
    _reset_checkpoint(conn)
    _insert_order(conn, "idem@example.com")
    conn.commit()

    assert _run_worker().returncode == 0
    committed_db_session.expire_all()
    count = conn.execute(text("SELECT COUNT(*) FROM order_contact_email")).fetchone()[0]

    assert _run_worker().returncode == 0
    committed_db_session.expire_all()
    assert conn.execute(text("SELECT COUNT(*) FROM order_contact_email")).fetchone()[0] == count


@pytest.mark.require_phase(*_PHASES)
def test_checkpoint_update(committed_db_session):
    """Checkpoint advances after a batch. Req 6.4"""
    conn = committed_db_session.connection()
    _reset_checkpoint(conn)
    order_id = _insert_order(conn, "ckpt@example.com")
    conn.commit()

    assert _run_worker().returncode == 0
    committed_db_session.expire_all()

    row = conn.execute(
        text("SELECT last_order_id, rows_processed FROM backfill_progress WHERE job_name=:j"),
        {"j": _JOB},
    ).fetchone()
    assert row.last_order_id >= order_id and row.rows_processed > 0


@pytest.mark.require_phase(*_PHASES)
def test_clean_exit_when_empty(committed_db_session):
    """Worker exits 0 with 'backfill complete' when no rows remain. Req 6.4"""
    conn = committed_db_session.connection()
    _reset_checkpoint(conn)
    _insert_order(conn, "done@example.com")
    conn.commit()

    for _ in range(2):
        result = _run_worker()
        assert result.returncode == 0 and "backfill complete" in result.stdout


def test_log_batch_fields():
    """log_batch emits JSON with last_order_id, inserted, elapsed_ms. Req 6.7"""
    buf = io.StringIO()
    sys.stdout, old = buf, sys.stdout
    try:
        metrics.log_batch(42, 100, 12.5)
    finally:
        sys.stdout = old

    data = json.loads(buf.getvalue().strip())
    assert data == {"last_order_id": 42, "inserted": 100, "elapsed_ms": 12.5}
