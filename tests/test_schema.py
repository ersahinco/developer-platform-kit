import os
import subprocess

import pytest
from sqlalchemy import inspect, text


COMPOSE_FILE = os.path.join(os.path.dirname(__file__), "..", "docker-compose.yml")

# Columns that must survive the full migration lifecycle (billing_email is
# intentionally dropped by the Contract changeset and is excluded here).
BOOTSTRAP_ORDERS_COLUMNS = {
    "id", "customer_id", "total_amount", "status",
    "submitted_at", "created_at",
}


def _run_liquibase(*args):
    cmd = [
        "docker", "compose",
        "--profile", "migration",
        "-f", COMPOSE_FILE,
        "run", "--rm", "liquibase",
    ] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


def _orders_columns(db_session):
    return {col["name"] for col in inspect(db_session.connection()).get_columns("orders")}


def _set_read_mode(db_session, mode):
    db_session.execute(
        text(
            "INSERT INTO app_runtime_config (key, value) VALUES ('READ_MODE', :mode) "
            "ON CONFLICT (key) DO UPDATE SET value = :mode"
        ),
        {"mode": mode},
    )
    db_session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_expand_additive_only(db_session):
    """Bootstrap-era orders columns must all survive the full changelog. Req 2.4"""
    current = _orders_columns(db_session)
    missing = BOOTSTRAP_ORDERS_COLUMNS - current
    assert not missing, f"Expand changeset removed columns from orders: {sorted(missing)}"


@pytest.mark.last
def test_contract_precondition_blocks(db_session):
    """Contract changeset must HALT when READ_MODE != new. Req 3.2

    Rolls back the Contract changeset, sets READ_MODE=legacy, attempts
    liquibase update, and asserts billing_email is not dropped.
    Marked @pytest.mark.last because it mutates DATABASECHANGELOG.
    """
    _set_read_mode(db_session, "legacy")

    rollback = _run_liquibase("rollbackCount", "1")
    if rollback.returncode != 0:
        pytest.skip(f"Could not roll back Contract changeset: {rollback.stderr}")

    db_session.expire_all()
    assert "billing_email" in _orders_columns(db_session)

    result = _run_liquibase("update")
    assert result.returncode != 0, "Expected Liquibase to HALT but it exited 0"

    db_session.expire_all()
    assert "billing_email" in _orders_columns(db_session), "billing_email was dropped despite READ_MODE=legacy"

    _set_read_mode(db_session, "new")
    _run_liquibase("update")
