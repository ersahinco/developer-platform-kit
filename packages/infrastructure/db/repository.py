"""Compatibility facade for SQLAlchemy/Postgres adapters.

Keep the public import path stable while the implementation is split by
capability under ``infrastructure.db``.
"""

from infrastructure.db.config_store import SQLAlchemyConfigStore
from infrastructure.db.config_store import _read_mode_cache, _write_mode_cache
from infrastructure.db.idempotency import SQLAlchemyIdempotencyRepository
from infrastructure.db.order_event_receipts import (
    SQLAlchemyOrderEventReceiptRepository,
)
from infrastructure.db.orders import (
    SQLAlchemyCustomerRepository,
    SQLAlchemyOrderRepository,
)
from infrastructure.db.outbox import SQLAlchemyOutboxRepository

__all__ = [
    "SQLAlchemyConfigStore",
    "SQLAlchemyCustomerRepository",
    "SQLAlchemyIdempotencyRepository",
    "SQLAlchemyOrderEventReceiptRepository",
    "SQLAlchemyOrderRepository",
    "SQLAlchemyOutboxRepository",
    "_read_mode_cache",
    "_write_mode_cache",
]
