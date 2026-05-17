from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session


def make_customer(
    session: Session,
    *,
    name: str = "Test Customer",
) -> int:
    """Insert a customers row and return its id."""
    # Advance the sequence past any rows already in the table so the INSERT
    # does not collide with seeded data that was inserted with explicit ids.
    session.execute(
        text(
            "SELECT setval('customers_id_seq', "
            "GREATEST(nextval('customers_id_seq'), "
            "(SELECT COALESCE(MAX(id), 0) + 1 FROM customers)))"
        )
    )
    row = session.execute(
        text(
            "INSERT INTO customers (name, created_at) "
            "VALUES (:name, NOW()) RETURNING id"
        ),
        {"name": name},
    ).fetchone()
    assert row is not None
    session.commit()
    return row.id


def make_order(
    session: Session,
    *,
    customer_id: int = 1,
    total_amount: Decimal = Decimal("10.00"),
    status: str = "SUBMITTED",
    billing_email: str | None = None,
) -> int:
    """Insert an orders row and return its id."""
    row = session.execute(
        text(
            "INSERT INTO orders "
            "(customer_id, total_amount, status, submitted_at, created_at, billing_email) "
            "VALUES (:cid, :amt, :status, NOW(), NOW(), :email) RETURNING id"
        ),
        {
            "cid": customer_id,
            "amt": total_amount,
            "status": status,
            "email": billing_email,
        },
    ).fetchone()
    assert row is not None
    session.commit()
    return row.id
