"""
conftest.py — Shared fixtures and phase-aware skip logic.

Migration phase detection
-------------------------
At session start, conftest inspects the live DB and env to determine which
migration phase the stack is currently in:

  legacy            WRITE_MODE=legacy, billing_email column exists
  dual              WRITE_MODE=dual,   billing_email column exists
  switch            WRITE_MODE=dual,   billing_email column exists, READ_MODE=new
  new_pre_contract  WRITE_MODE=new,    billing_email column exists (app stopped writing it)
  post_contract     billing_email column dropped

Tests declare which phases they are valid for with:

    @pytest.mark.require_phase("legacy", "dual")

If the current phase is not in the list, the test is skipped automatically.
No per-test DB introspection needed.
"""

import os
import sys
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Bootstrap: load .env and make worker/src importable
# ---------------------------------------------------------------------------

_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

_WORKER_SRC = os.path.join(os.path.dirname(__file__), "..", "worker", "src")
if _WORKER_SRC not in sys.path:
    sys.path.insert(0, _WORKER_SRC)

# ---------------------------------------------------------------------------
# Phase detection — runs once per session
# ---------------------------------------------------------------------------

def _detect_phase(engine) -> str:
    """
    Derive the current migration phase from the live DB + WRITE_MODE env var.

    Schema state (billing_email column) is the authoritative signal for whether
    the Contract has been applied. WRITE_MODE and READ_MODE distinguish the
    earlier phases.
    """
    write_mode = os.environ.get("WRITE_MODE", "legacy")

    with engine.connect() as conn:
        col_exists = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'orders' AND column_name = 'billing_email'"
            )
        ).fetchone() is not None

        if not col_exists:
            return "post_contract"

        read_mode_row = conn.execute(
            text("SELECT value FROM app_runtime_config WHERE key = 'READ_MODE'")
        ).fetchone()
        read_mode = read_mode_row[0] if read_mode_row else os.environ.get("READ_MODE", "legacy")

    if write_mode == "legacy":
        return "legacy"
    if write_mode == "dual" and read_mode == "new":
        return "switch"
    if write_mode == "dual":
        return "dual"
    if write_mode == "new" and col_exists:
        return "new_pre_contract"
    return "post_contract"


# ---------------------------------------------------------------------------
# Session-scoped engine and phase
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True, pool_size=5, max_overflow=0)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def migration_phase(db_engine) -> str:
    """Current migration phase string, detected once per test session."""
    return _detect_phase(db_engine)


# Detect phase once at import time — used by pytest_runtest_setup hook which
# runs before fixtures and cannot access session-scoped fixtures directly.
_cached_phase: str = _detect_phase(
    create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True, pool_size=1, max_overflow=0)
)

# ---------------------------------------------------------------------------
# require_phase mark — skip tests not valid for the current phase
# ---------------------------------------------------------------------------

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "require_phase(*phases): skip test unless current migration phase is in phases",
    )


def pytest_runtest_setup(item):
    marker = item.get_closest_marker("require_phase")
    if marker is None:
        return
    required = set(marker.args)
    if _cached_phase not in required:
        pytest.skip(f"phase={_cached_phase!r} — test requires phase in {sorted(required)}")


# ---------------------------------------------------------------------------
# DB session fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_session(db_engine):
    """Per-test session that rolls back after each test."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def committed_db_session(db_engine):
    """
    Per-test session that commits so subprocess workers can see the data.
    Cleans up rows inserted during the test using a high-water mark on orders.id.
    Also restores the backfill_progress checkpoint to its pre-test value.
    """
    Session = sessionmaker(bind=db_engine)
    session = Session()
    max_order_id_before = session.execute(
        text("SELECT COALESCE(MAX(id), 0) FROM orders")
    ).scalar()
    checkpoint_before = session.execute(
        text(
            "SELECT last_order_id, rows_processed FROM backfill_progress "
            "WHERE job_name = 'order_contact_email_backfill'"
        )
    ).fetchone()
    try:
        yield session
    finally:
        try:
            session.close()
        except Exception:
            pass
        with db_engine.connect() as conn:
            conn.execute(
                text("DELETE FROM order_contact_email WHERE order_id > :max_id"),
                {"max_id": max_order_id_before},
            )
            conn.execute(
                text("DELETE FROM orders WHERE id > :max_id"),
                {"max_id": max_order_id_before},
            )
            if checkpoint_before is not None:
                conn.execute(
                    text(
                        "INSERT INTO backfill_progress (job_name, last_order_id, rows_processed) "
                        "VALUES ('order_contact_email_backfill', :last_id, :processed) "
                        "ON CONFLICT (job_name) DO UPDATE "
                        "SET last_order_id = :last_id, rows_processed = :processed"
                    ),
                    {"last_id": checkpoint_before.last_order_id, "processed": checkpoint_before.rows_processed},
                )
            else:
                conn.execute(
                    text("DELETE FROM backfill_progress WHERE job_name = 'order_contact_email_backfill'")
                )
            conn.commit()


# ---------------------------------------------------------------------------
# HTTP client fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def base_url():
    return os.environ.get("BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="function")
def http_client(base_url):
    with httpx.Client(base_url=base_url) as client:
        yield client


# ---------------------------------------------------------------------------
# Ordering hook — @pytest.mark.last runs after everything else
# ---------------------------------------------------------------------------

def pytest_collection_modifyitems(items):
    last_items = [i for i in items if i.get_closest_marker("last")]
    rest = [i for i in items if not i.get_closest_marker("last")]
    items[:] = rest + last_items
