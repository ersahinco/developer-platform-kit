import json
import os
import subprocess

from sqlalchemy import text

from tests.helpers.runtime_env import direct_postgres_url

_WORKER_SRC = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "apps", "backfill_worker"
)


def _run_worker(**extra_env):
    env = {**os.environ, **extra_env}
    if not env.get("BACKFILL_DATABASE_URL"):
        env["BACKFILL_DATABASE_URL"] = direct_postgres_url(env)
    return subprocess.run(
        [
            "uv",
            "run",
            "--package",
            "aws-sdlc-containers-backfill-worker",
            "python",
            "-m",
            "backfill_worker.main",
        ],
        cwd=_WORKER_SRC,
        env=env,
        capture_output=True,
        text=True,
    )


def _insert_order(conn, billing_email="seed@example.com"):
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


def test_backfill_worker_exits_zero_and_emits_json_log(committed_db_session):
    conn = committed_db_session.connection()
    _insert_order(conn, "happy@example.com")
    conn.commit()

    result = _run_worker()
    assert result.returncode == 0, result.stderr

    log_lines = [line for line in result.stdout.splitlines() if line.startswith("{")]
    assert log_lines, f"expected at least one JSON log line; stdout={result.stdout!r}"
    # Verify the first log line is valid JSON
    json.loads(log_lines[0])


def test_backfill_worker_bounded_run_emits_paused_or_complete(committed_db_session):
    conn = committed_db_session.connection()
    _insert_order(conn, "bounded@example.com")
    conn.commit()

    result = _run_worker(
        BACKFILL_MAX_BATCHES="1",
        BACKFILL_BATCH_SIZE="1",
    )
    assert result.returncode == 0, result.stderr

    assert "backfill_paused" in result.stdout or "backfill_complete" in result.stdout, (
        f"expected 'backfill_paused' or 'backfill_complete' in stdout; "
        f"stdout={result.stdout!r}"
    )
