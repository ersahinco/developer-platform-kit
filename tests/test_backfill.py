"""
test_backfill.py — Custom backfill worker tests.

The worker copies existing orders.billing_email rows into order_contact_email.

Tests run the worker as a subprocess against the live DB, which is the same
execution path used in production (one-off ECS task).
"""

import json
import os
import subprocess
from urllib.parse import urlparse, urlunparse

from sqlalchemy import text

_WORKER_SRC = os.path.join(
    os.path.dirname(__file__), "..", "apps", "backfill-worker", "src"
)
_JOB = "order_contact_email_backfill"


def _run_worker(**extra_env):
    env = {**os.environ, **extra_env}
    # Always derive BACKFILL_DATABASE_URL from DATABASE_URL so the worker subprocess
    # reaches Postgres on localhost, not the Docker-internal hostname.
    # conftest.py loads .env via load_dotenv which puts BACKFILL_DATABASE_URL=...@db:5432
    # into os.environ — that Docker hostname is unreachable from the host machine.
    # Overwrite unconditionally unless the caller explicitly passed one in extra_env.
    if "BACKFILL_DATABASE_URL" not in extra_env:
        db_url = env.get(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:6432/aws_sdlc_containers",
        )
        # Parse and replace host/port so the worker subprocess reaches Postgres
        # on localhost rather than the Docker-internal hostname from .env.
        parsed = urlparse(db_url)
        direct = parsed._replace(
            netloc=f"{parsed.username}:{parsed.password}@localhost:5432"
        )
        env["BACKFILL_DATABASE_URL"] = urlunparse(direct)
    # uv run --package resolves the worker's deps from the workspace without
    # hardcoding a venv path. The module entrypoint matches the Docker container.
    return subprocess.run(
        [
            "uv",
            "run",
            "--package",
            "aws-sdlc-containers-backfill-worker",
            "python",
            "-m",
            "aws_sdlc_backfill_worker.main",
        ],
        cwd=_WORKER_SRC,
        env=env,
        capture_output=True,
        text=True,
    )


def _insert_order(conn, billing_email=None):
    return (
        conn.execute(
            text(
                "INSERT INTO orders (customer_id, total_amount, status, submitted_at, billing_email) "
                "VALUES (1, 10.00, 'SUBMITTED', NOW(), :e) RETURNING id"
            ),
            {"e": billing_email},
        )
        .fetchone()
        .id
    )


def _reset_checkpoint(conn):
    conn.execute(text("DELETE FROM backfill_progress WHERE job_name=:j"), {"j": _JOB})
    conn.commit()


def test_rows_with_billing_email_are_backfilled_null_rows_are_skipped(
    committed_db_session,
):
    """Rows with billing_email are copied to order_contact_email; NULL rows are skipped."""
    conn = committed_db_session.connection()
    _reset_checkpoint(conn)
    id_a = _insert_order(conn, "a@example.com")
    id_null = _insert_order(conn, None)
    id_b = _insert_order(conn, "b@example.com")
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
    assert inserted == {id_a, id_b}


def test_running_worker_twice_produces_the_same_row_count(committed_db_session):
    """Backfill is idempotent — ON CONFLICT DO NOTHING prevents duplicate rows."""
    conn = committed_db_session.connection()
    _reset_checkpoint(conn)
    _insert_order(conn, "idem@example.com")
    conn.commit()

    assert _run_worker().returncode == 0
    committed_db_session.expire_all()
    count = conn.execute(text("SELECT COUNT(*) FROM order_contact_email")).fetchone()[0]

    assert _run_worker().returncode == 0
    committed_db_session.expire_all()
    assert (
        conn.execute(text("SELECT COUNT(*) FROM order_contact_email")).fetchone()[0]
        == count
    )


def test_checkpoint_advances_after_each_batch(committed_db_session):
    """Checkpoint cursor advances so a restart replays only unprocessed rows."""
    conn = committed_db_session.connection()
    _reset_checkpoint(conn)
    order_id = _insert_order(conn, "ckpt@example.com")
    conn.commit()

    assert _run_worker().returncode == 0
    committed_db_session.expire_all()

    row = conn.execute(
        text(
            "SELECT last_order_id, rows_processed FROM backfill_progress WHERE job_name=:j"
        ),
        {"j": _JOB},
    ).fetchone()
    assert row.last_order_id >= order_id and row.rows_processed > 0


def test_worker_exits_cleanly_when_no_rows_remain(committed_db_session):
    """Worker exits 0 with 'backfill complete' when there is nothing left to process."""
    conn = committed_db_session.connection()
    _reset_checkpoint(conn)
    _insert_order(conn, "done@example.com")
    conn.commit()

    for _ in range(2):
        result = _run_worker()
        assert result.returncode == 0
        assert "backfill complete" in result.stdout


def test_each_batch_emits_a_structured_json_log_line(committed_db_session):
    """Each processed batch emits a JSON log line with last_order_id, inserted, elapsed_ms."""
    conn = committed_db_session.connection()
    _reset_checkpoint(conn)
    _insert_order(conn, "log@example.com")
    conn.commit()

    result = _run_worker()
    assert result.returncode == 0

    log_lines = [line for line in result.stdout.splitlines() if line.startswith("{")]
    assert log_lines, "expected at least one JSON log line"
    data = json.loads(log_lines[0])
    assert {"last_order_id", "inserted", "elapsed_ms"} <= data.keys()
