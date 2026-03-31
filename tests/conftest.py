"""
conftest.py — Shared fixtures and phase-aware skip logic.

Migration phases:
  legacy            WRITE_MODE=legacy, billing_email column exists
  dual              WRITE_MODE=dual,   billing_email column exists
  switch            WRITE_MODE=dual,   READ_MODE=new, billing_email column exists
  new_pre_contract  WRITE_MODE=new,    billing_email column exists
  post_contract     billing_email column dropped
"""

import os
import sys
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent / "worker" / "src"))

# ---------------------------------------------------------------------------
# Phase detection
# ---------------------------------------------------------------------------

def _detect_phase(engine) -> str:
    write_mode = os.environ.get("WRITE_MODE", "legacy")
    with engine.connect() as conn:
        col_exists = conn.execute(
            text("SELECT 1 FROM information_schema.columns "
                 "WHERE table_name='orders' AND column_name='billing_email'")
        ).fetchone() is not None
        if not col_exists:
            return "post_contract"
        row = conn.execute(
            text("SELECT value FROM app_runtime_config WHERE key='READ_MODE'")
        ).fetchone()
        read_mode = row[0] if row else os.environ.get("READ_MODE", "legacy")

    if write_mode == "legacy":
        # legacy+new is not a valid migration phase — no tests should run
        return "legacy_invalid" if read_mode == "new" else "legacy"
    if write_mode == "dual":
        return "switch" if read_mode == "new" else "dual"
    if write_mode == "new":
        # new+legacy is not a valid migration phase — no tests should run
        return "new_invalid" if read_mode == "legacy" else "new_pre_contract"
    return "post_contract"


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "require_phase(*phases): skip unless current migration phase is in phases"
    )
    config.addinivalue_line("markers", "last: run after all other tests")


# Cached once at collection time for the skip hook.
_cached_phase: str = _detect_phase(
    create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True, pool_size=1, max_overflow=0)
)


def pytest_runtest_setup(item):
    marker = item.get_closest_marker("require_phase")
    if marker and _cached_phase not in set(marker.args):
        pytest.skip(f"phase={_cached_phase!r} not in {sorted(marker.args)}")


def pytest_collection_modifyitems(items):
    last = [i for i in items if i.get_closest_marker("last")]
    rest = [i for i in items if not i.get_closest_marker("last")]
    items[:] = rest + last


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True, pool_size=5, max_overflow=0)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def migration_phase(db_engine) -> str:
    return _detect_phase(db_engine)


@pytest.fixture
def db_session(db_engine):
    """Rolls back after each test — no data persists."""
    session = sessionmaker(bind=db_engine)()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def committed_db_session(db_engine):
    """Commits so subprocess workers can see data; cleans up afterwards."""
    session = sessionmaker(bind=db_engine)()
    watermark = session.execute(text("SELECT COALESCE(MAX(id), 0) FROM orders")).scalar()
    ckpt = session.execute(
        text("SELECT last_order_id, rows_processed FROM backfill_progress "
             "WHERE job_name='order_contact_email_backfill'")
    ).fetchone()
    try:
        yield session
    finally:
        session.close()
        with db_engine.connect() as conn:
            conn.execute(text("DELETE FROM order_contact_email WHERE order_id > :m"), {"m": watermark})
            conn.execute(text("DELETE FROM orders WHERE id > :m"), {"m": watermark})
            if ckpt:
                conn.execute(
                    text("INSERT INTO backfill_progress (job_name, last_order_id, rows_processed) "
                         "VALUES ('order_contact_email_backfill', :l, :p) "
                         "ON CONFLICT (job_name) DO UPDATE SET last_order_id=:l, rows_processed=:p"),
                    {"l": ckpt.last_order_id, "p": ckpt.rows_processed},
                )
            else:
                conn.execute(text("DELETE FROM backfill_progress WHERE job_name='order_contact_email_backfill'"))
            conn.commit()


@pytest.fixture
def base_url():
    return os.environ.get("BASE_URL", "http://localhost:8000")


@pytest.fixture
def http_client(base_url):
    with httpx.Client(base_url=base_url) as client:
        yield client


# ---------------------------------------------------------------------------
# Shared helpers (used across test modules)
# ---------------------------------------------------------------------------

def post_order(http_client, billing_email="test@example.com", **kwargs):
    payload = {"customer_id": 1, "total_amount": 10.00, "status": "SUBMITTED", **kwargs}
    if billing_email is not None:
        payload["billing_email"] = billing_email
    resp = http_client.post("/orders", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def contact_row(db_session, order_id):
    return db_session.execute(
        text("SELECT billing_email FROM order_contact_email WHERE order_id=:oid"),
        {"oid": order_id},
    ).fetchone()
