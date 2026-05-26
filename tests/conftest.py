"""
conftest.py — Shared fixtures for integration tests.

Migration phases and which tests run in each:

  legacy           — WRITE_MODE=legacy,  READ_MODE=legacy
                     App deployed, order_contact_email does not yet exist.
                     Writes go only to orders.billing_email.

  dual             — WRITE_MODE=dual,    READ_MODE=legacy
                     order_contact_email exists. Writes go to both tables.
                     Reads still from orders.billing_email.
                     Backfill worker running.

  switch           — WRITE_MODE=dual,    READ_MODE=new
                     Backfill complete. Reads switched to order_contact_email.
                     Writes still dual so a rollback of READ_MODE is safe.

  new_pre_contract — WRITE_MODE=new,     READ_MODE=new
                     Writes stop touching orders.billing_email.
                     Pre-condition for the contract (drop column) phase.

  post_contract    — orders.billing_email column dropped.
                     WRITE_MODE=new, READ_MODE=new.

The `require_phase` marker skips a test when the live DB is not in one of the
declared phases. Phase is detected from app_runtime_config at session start.
"""

import os
import sys
from pathlib import Path
from collections.abc import Generator
from typing import Any

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
for path in (
    ROOT / "apps",
    ROOT / "examples",
    ROOT / "packages",
):
    sys.path.insert(0, str(path))

from infrastructure.config import load_env_file  # noqa: E402

load_env_file(Path(__file__).parent.parent / ".env")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:6432/aws_sdlc_containers",
)


# ---------------------------------------------------------------------------
# Phase detection
# ---------------------------------------------------------------------------


def _detect_phase(engine: Engine) -> str:
    """Derive the current migration phase from app_runtime_config + schema state."""
    with engine.connect() as conn:
        col_exists = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name='orders' AND column_name='billing_email'"
            )
        ).fetchone()
        if col_exists is None:
            return "post_contract"

        def cfg(key: str) -> str | None:
            row = conn.execute(
                text("SELECT value FROM app_runtime_config WHERE key=:k"), {"k": key}
            ).fetchone()
            return row[0] if row else None

        write_mode = cfg("WRITE_MODE") or "legacy"
        read_mode = cfg("READ_MODE") or "legacy"

    if write_mode == "legacy":
        return "legacy"
    if write_mode == "dual" and read_mode == "legacy":
        return "dual"
    if write_mode == "dual" and read_mode == "new":
        return "switch"
    if write_mode == "new" and read_mode == "new":
        return "new_pre_contract"
    return "legacy"


_BACKFILL_JOB = "order_contact_email_backfill"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def db_engine() -> Generator[Engine, None, None]:
    # NullPool: tests connect via PgBouncer (transaction mode) — same reason as
    # the app. A session-scoped pool would hold server connections idle between
    # tests, defeating PgBouncer's multiplexing.
    engine = create_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """Rolls back after each test — no data persists."""
    session = sessionmaker(db_engine)()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def committed_db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """Commits so the running app and worker subprocess can see data; cleans up afterwards."""
    session = sessionmaker(db_engine)()
    watermark = session.execute(
        text("SELECT COALESCE(MAX(id), 0) FROM orders")
    ).scalar()
    ckpt = session.execute(
        text(
            "SELECT last_order_id, rows_processed FROM backfill_progress "
            "WHERE job_name=:j"
        ),
        {"j": _BACKFILL_JOB},
    ).fetchone()
    try:
        yield session
    finally:
        session.close()
        with db_engine.connect() as conn:
            conn.execute(
                text(
                    "DELETE FROM outbox_messages "
                    "WHERE aggregate_type = 'order' AND aggregate_id > :m"
                ),
                {"m": watermark},
            )
            conn.execute(
                text(
                    "DELETE FROM event_receipts "
                    "WHERE aggregate_type = 'order' AND aggregate_id > :m"
                ),
                {"m": watermark},
            )
            conn.execute(
                text("DELETE FROM order_contact_email WHERE order_id > :m"),
                {"m": watermark},
            )
            conn.execute(text("DELETE FROM orders WHERE id > :m"), {"m": watermark})
            if ckpt:
                conn.execute(
                    text(
                        "INSERT INTO backfill_progress (job_name, last_order_id, rows_processed) "
                        "VALUES (:j, :l, :p) "
                        "ON CONFLICT (job_name) DO UPDATE SET last_order_id=:l, rows_processed=:p"
                    ),
                    {
                        "j": _BACKFILL_JOB,
                        "l": ckpt.last_order_id,
                        "p": ckpt.rows_processed,
                    },
                )
            else:
                conn.execute(
                    text("DELETE FROM backfill_progress WHERE job_name=:j"),
                    {"j": _BACKFILL_JOB},
                )
            conn.commit()


@pytest.fixture
def base_url() -> str:
    return os.environ.get("BASE_URL", "http://localhost:8000")


@pytest.fixture
def http_client(base_url: str) -> Generator[httpx.Client, None, None]:
    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        yield client


# ---------------------------------------------------------------------------
# require_phase marker
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip tests whose require_phase marker does not match the live DB phase."""
    # Phase detection requires a DB connection — skip if DATABASE_URL is absent
    # (e.g. during collection-only runs or import checks).
    if "DATABASE_URL" not in os.environ:
        return

    engine: Engine | None = None
    try:
        engine = create_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
        phase = _detect_phase(engine)
    except Exception:
        return  # can't connect — don't skip anything, let tests fail naturally
    finally:
        if engine is not None:
            engine.dispose()

    for item in items:
        marker = item.get_closest_marker("require_phase")
        if marker and phase not in marker.args:
            item.add_marker(
                pytest.mark.skip(reason=f"phase={phase!r} not in {marker.args}")
            )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def post_order(
    http_client: httpx.Client,
    billing_email: str | None = "test@example.com",
    **kwargs: Any,
) -> int:
    # "10.00" as a string so Pydantic parses it as Decimal, not float.
    payload = {
        "customer_id": 1,
        "total_amount": "10.00",
        **kwargs,
    }
    if billing_email is not None:
        payload["billing_email"] = billing_email
    resp = http_client.post("/orders", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def contact_row(db_session: Session, order_id: int):
    return db_session.execute(
        text("SELECT billing_email FROM order_contact_email WHERE order_id=:oid"),
        {"oid": order_id},
    ).fetchone()
