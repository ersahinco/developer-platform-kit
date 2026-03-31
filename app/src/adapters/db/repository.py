from __future__ import annotations

import datetime
import threading
import time

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from adapters.db.models import AppRuntimeConfigModel, OrderContactEmailModel, OrderModel
from config import Settings
from domain.order import Order
from domain.ports import ConfigStore, OrderRepository


class SQLAlchemyOrderRepository(OrderRepository):
    def __init__(self, session: Session, settings: Settings, config_store: ConfigStore) -> None:
        self._session = session
        self._settings = settings
        self._config_store = config_store

    def create_order(self, customer_id: int, total_amount: float, status: str, billing_email: str | None) -> Order:
        write_mode = self._settings.write_mode

        now = datetime.datetime.now(tz=datetime.timezone.utc)
        order_row = OrderModel(
            customer_id=customer_id,
            total_amount=total_amount,
            status=status,
            submitted_at=now,
            # legacy + dual modes still write to orders.billing_email so the
            # legacy read path returns the correct value.
            billing_email=billing_email if write_mode in ("legacy", "dual") else None,
        )
        self._session.add(order_row)
        self._session.flush()

        if billing_email is not None and write_mode in ("dual", "new"):
            stmt = (
                pg_insert(OrderContactEmailModel)
                .values(order_id=order_row.id, billing_email=billing_email, source="app-dual-write", updated_at=now)
                .on_conflict_do_update(
                    index_elements=["order_id"],
                    set_={"billing_email": billing_email, "source": "app-dual-write", "updated_at": now},
                )
            )
            self._session.execute(stmt)

        self._session.commit()
        self._session.refresh(order_row)

        return Order(
            id=order_row.id,
            customer_id=order_row.customer_id,
            total_amount=float(order_row.total_amount),
            status=order_row.status,
            submitted_at=order_row.submitted_at,
            created_at=order_row.created_at,
            billing_email=billing_email,
        )

    def get_order(self, order_id: int) -> Order | None:
        order_row = self._session.get(OrderModel, order_id)
        if order_row is None:
            return None

        if self._config_store.get_read_mode() == "new":
            # Switch phase: read from the new table.
            contact = self._session.get(OrderContactEmailModel, order_id)
            resolved_email = contact.billing_email if contact else None
        else:
            # Legacy phase: read from orders.billing_email (dropped after Contract).
            resolved_email = order_row.billing_email

        return Order(
            id=order_row.id,
            customer_id=order_row.customer_id,
            total_amount=float(order_row.total_amount),
            status=order_row.status,
            submitted_at=order_row.submitted_at,
            created_at=order_row.created_at,
            billing_email=resolved_email,
        )


class SQLAlchemyConfigStore(ConfigStore):
    _KEY = "READ_MODE"
    _TTL_SECONDS = 5  # re-read from DB at most once every 5 seconds

    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def get_read_mode(self) -> str:
        return _read_mode_cache.get(self._session, self._settings.read_mode)

    def set_read_mode(self, mode: str) -> None:
        stmt = (
            pg_insert(AppRuntimeConfigModel)
            .values(key=self._KEY, value=mode)
            .on_conflict_do_update(index_elements=["key"], set_={"value": mode})
        )
        self._session.execute(stmt)
        self._session.commit()
        _read_mode_cache.invalidate()


class _ReadModeCache:
    """
    Process-level read-through cache for READ_MODE.

    Double-checked locking: on a cache miss, one thread queries the DB while
    others wait. When the lock is released, waiting threads see a warm cache
    and return immediately without hitting the DB again.

    On write, invalidate() is called immediately so the next request re-reads
    from the DB rather than serving a stale value for up to TTL seconds.

    Production note: in a multi-instance deployment, invalidate() only clears
    the local process cache. Other instances serve stale values until their TTL
    expires. Replace with pub/sub invalidation (Redis, SNS) for instant
    cross-instance propagation.
    """

    def __init__(self, ttl: float = 5.0) -> None:
        self._ttl = ttl
        self._value: str | None = None
        self._expires_at: float = 0.0
        self._lock = threading.Lock()

    def get(self, session: Session, fallback: str) -> str:
        # Fast path: cache is warm, no lock needed.
        now = time.monotonic()
        if self._value is not None and now < self._expires_at:
            return self._value

        # Slow path: acquire lock, then check again — another thread may have
        # already populated the cache while we were waiting.
        with self._lock:
            now = time.monotonic()
            if self._value is not None and now < self._expires_at:
                return self._value
            row = session.get(AppRuntimeConfigModel, "READ_MODE")
            self._value = row.value if row else fallback
            self._expires_at = time.monotonic() + self._ttl
            return self._value

    def invalidate(self) -> None:
        with self._lock:
            self._expires_at = 0.0


_read_mode_cache = _ReadModeCache(ttl=5.0)
