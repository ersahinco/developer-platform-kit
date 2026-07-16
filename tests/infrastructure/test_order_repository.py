from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from infrastructure.db.orders import SQLAlchemyOrderRepository
from tests.fixtures import make_customer


def _set_modes(session: Session, *, write: str, read: str) -> None:
    """Upsert WRITE_MODE and READ_MODE in app_runtime_config and invalidate caches."""
    for key, val in [("WRITE_MODE", write), ("READ_MODE", read)]:
        session.execute(
            text(
                "INSERT INTO app_runtime_config (key, value) VALUES (:k, :v) "
                "ON CONFLICT (key) DO UPDATE SET value = :v"
            ),
            {"k": key, "v": val},
        )
    session.commit()
    from infrastructure.db.config_store import _read_mode_cache, _write_mode_cache

    _read_mode_cache.invalidate()
    _write_mode_cache.invalidate()


def _get_mode(session: Session, key: str) -> str | None:
    """Read a single app_runtime_config value."""
    row = session.execute(
        text("SELECT value FROM app_runtime_config WHERE key = :k"),
        {"k": key},
    ).fetchone()
    return row[0] if row else None


def test_write_mode_legacy(committed_db_session: Session) -> None:
    """WRITE_MODE=legacy: billing_email in orders.billing_email, no row in order_contact_email."""
    orig_write = _get_mode(committed_db_session, "WRITE_MODE")
    orig_read = _get_mode(committed_db_session, "READ_MODE")
    try:
        _set_modes(committed_db_session, write="legacy", read="legacy")
        customer_id = make_customer(committed_db_session)
        repo = SQLAlchemyOrderRepository(committed_db_session)

        order = repo.create_order(
            customer_id=customer_id,
            total_amount=Decimal("25.00"),
            billing_email="legacy@example.com",
        )

        # orders.billing_email should hold the value
        orders_row = committed_db_session.execute(
            text("SELECT billing_email FROM orders WHERE id = :oid"),
            {"oid": order.id},
        ).fetchone()
        assert orders_row is not None
        assert orders_row[0] == "legacy@example.com"

        # no row in order_contact_email
        contact_row = committed_db_session.execute(
            text("SELECT billing_email FROM order_contact_email WHERE order_id = :oid"),
            {"oid": order.id},
        ).fetchone()
        assert contact_row is None
    finally:
        if orig_write is not None and orig_read is not None:
            _set_modes(committed_db_session, write=orig_write, read=orig_read)


def test_write_mode_dual(committed_db_session: Session) -> None:
    """WRITE_MODE=dual: billing_email in both orders.billing_email and order_contact_email."""
    orig_write = _get_mode(committed_db_session, "WRITE_MODE")
    orig_read = _get_mode(committed_db_session, "READ_MODE")
    try:
        _set_modes(committed_db_session, write="dual", read="legacy")
        customer_id = make_customer(committed_db_session)
        repo = SQLAlchemyOrderRepository(committed_db_session)

        order = repo.create_order(
            customer_id=customer_id,
            total_amount=Decimal("30.00"),
            billing_email="dual@example.com",
        )

        # orders.billing_email should hold the value
        orders_row = committed_db_session.execute(
            text("SELECT billing_email FROM orders WHERE id = :oid"),
            {"oid": order.id},
        ).fetchone()
        assert orders_row is not None
        assert orders_row[0] == "dual@example.com"

        # order_contact_email should also hold the value
        contact_row = committed_db_session.execute(
            text("SELECT billing_email FROM order_contact_email WHERE order_id = :oid"),
            {"oid": order.id},
        ).fetchone()
        assert contact_row is not None
        assert contact_row[0] == "dual@example.com"
    finally:
        if orig_write is not None and orig_read is not None:
            _set_modes(committed_db_session, write=orig_write, read=orig_read)


def test_write_mode_new(committed_db_session: Session) -> None:
    """WRITE_MODE=new: orders.billing_email is NULL, row in order_contact_email."""
    orig_write = _get_mode(committed_db_session, "WRITE_MODE")
    orig_read = _get_mode(committed_db_session, "READ_MODE")
    try:
        _set_modes(committed_db_session, write="new", read="new")
        customer_id = make_customer(committed_db_session)
        repo = SQLAlchemyOrderRepository(committed_db_session)

        order = repo.create_order(
            customer_id=customer_id,
            total_amount=Decimal("40.00"),
            billing_email="new@example.com",
        )

        # orders.billing_email should be NULL
        orders_row = committed_db_session.execute(
            text("SELECT billing_email FROM orders WHERE id = :oid"),
            {"oid": order.id},
        ).fetchone()
        assert orders_row is not None
        assert orders_row[0] is None

        # order_contact_email should hold the value
        contact_row = committed_db_session.execute(
            text("SELECT billing_email FROM order_contact_email WHERE order_id = :oid"),
            {"oid": order.id},
        ).fetchone()
        assert contact_row is not None
        assert contact_row[0] == "new@example.com"
    finally:
        if orig_write is not None and orig_read is not None:
            _set_modes(committed_db_session, write=orig_write, read=orig_read)


def test_write_mode_dual_none_billing_email(committed_db_session: Session) -> None:
    """WRITE_MODE=dual with billing_email=None: no row in order_contact_email."""
    orig_write = _get_mode(committed_db_session, "WRITE_MODE")
    orig_read = _get_mode(committed_db_session, "READ_MODE")
    try:
        _set_modes(committed_db_session, write="dual", read="legacy")
        customer_id = make_customer(committed_db_session)
        repo = SQLAlchemyOrderRepository(committed_db_session)

        order = repo.create_order(
            customer_id=customer_id,
            total_amount=Decimal("15.00"),
            billing_email=None,
        )

        # no row in order_contact_email when billing_email is None
        contact_row = committed_db_session.execute(
            text("SELECT billing_email FROM order_contact_email WHERE order_id = :oid"),
            {"oid": order.id},
        ).fetchone()
        assert contact_row is None
    finally:
        if orig_write is not None and orig_read is not None:
            _set_modes(committed_db_session, write=orig_write, read=orig_read)
