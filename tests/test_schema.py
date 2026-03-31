"""test_schema.py — Schema migration correctness tests. Req 2.4, 3.2"""

import os
import subprocess

import pytest
from sqlalchemy import inspect, text

_COMPOSE = os.path.join(os.path.dirname(__file__), "..", "docker-compose.yml")
_STABLE_COLUMNS = {"id", "customer_id", "total_amount", "status", "submitted_at", "created_at"}


def _liquibase(*args):
    return subprocess.run(
        ["docker", "compose", "--profile", "migration", "-f", _COMPOSE, "run", "--rm", "liquibase", *args],
        capture_output=True, text=True,
    )


def _orders_columns(db_session):
    return {c["name"] for c in inspect(db_session.connection()).get_columns("orders")}


def test_expand_additive_only(db_session):
    """Bootstrap-era orders columns must survive the full changelog. Req 2.4"""
    assert not (_STABLE_COLUMNS - _orders_columns(db_session))


@pytest.mark.last
def test_contract_precondition_blocks(db_session):
    """Contract changeset must HALT when READ_MODE != new. Req 3.2"""
    db_session.execute(
        text("INSERT INTO app_runtime_config (key, value) VALUES ('READ_MODE', 'legacy') "
             "ON CONFLICT (key) DO UPDATE SET value='legacy'")
    )
    db_session.commit()

    if _liquibase("rollbackCount", "1").returncode != 0:
        pytest.skip("Could not roll back Contract changeset")

    db_session.expire_all()
    assert "billing_email" in _orders_columns(db_session)

    result = _liquibase("update")
    assert result.returncode != 0, "Expected Liquibase to HALT but it exited 0"

    db_session.expire_all()
    assert "billing_email" in _orders_columns(db_session)

    # Restore
    db_session.execute(
        text("INSERT INTO app_runtime_config (key, value) VALUES ('READ_MODE', 'new') "
             "ON CONFLICT (key) DO UPDATE SET value='new'")
    )
    db_session.commit()
    _liquibase("update")
