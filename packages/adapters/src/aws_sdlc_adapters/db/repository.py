import datetime
import threading
import time
from decimal import Decimal
from typing import cast

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from aws_sdlc_adapters.db.models import (
    AppRuntimeConfigModel,
    CustomerModel,
    OrderContactEmailModel,
    OrderModel,
)
from aws_sdlc_core.customer import Customer
from aws_sdlc_core.order import Order, OrderStatus, ReadModeValue, WriteModeValue
from aws_sdlc_core.ports import ConfigStore, CustomerRepository, OrderRepository

_TTL_SECONDS = 5  # re-read app_runtime_config at most every 5 seconds


class _ConfigCache:
    """Thread-safe TTL cache for a single app_runtime_config key.

    The lock is always acquired on the slow path (cache miss or expiry).
    Uncontended lock acquisition is cheap enough that double-checked locking
    adds complexity without measurable benefit at this TTL and request rate.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._value: str | None = None
        self._expires_at: float = 0.0

    def get(self, session: Session, key: str) -> str:
        """Return the cached value, querying via *session* only on a cache miss."""
        with self._lock:
            now = time.monotonic()
            if now < self._expires_at and self._value is not None:
                return self._value
            row = session.get(AppRuntimeConfigModel, key)
            if row is None:
                raise RuntimeError(
                    f"app_runtime_config row for '{key}' is missing — "
                    "ensure the DB was seeded correctly (Liquibase changeset 002)."
                )
            self._value = row.value
            self._expires_at = time.monotonic() + _TTL_SECONDS
            return self._value

    def invalidate(self) -> None:
        with self._lock:
            self._expires_at = 0.0


_read_mode_cache = _ConfigCache()
_write_mode_cache = _ConfigCache()


class SQLAlchemyConfigStore(ConfigStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, key: str) -> str | None:
        row = self._session.get(AppRuntimeConfigModel, key)
        return row.value if row else None

    def set(self, key: str, value: str) -> None:
        stmt = (
            pg_insert(AppRuntimeConfigModel)
            .values(key=key, value=value)
            .on_conflict_do_update(index_elements=["key"], set_={"value": value})
        )
        self._session.execute(stmt)
        self._session.commit()
        # Invalidate the relevant cache so the next request sees the new value
        # within one request rather than waiting for TTL expiry.
        if key == "READ_MODE":
            _read_mode_cache.invalidate()
        elif key == "WRITE_MODE":
            _write_mode_cache.invalidate()


class SQLAlchemyOrderRepository(OrderRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def _write_mode(self) -> WriteModeValue:
        # cast: the DB stores a plain str; we trust the seeded values are valid.
        return cast(WriteModeValue, _write_mode_cache.get(self._session, "WRITE_MODE"))

    def _read_mode(self) -> ReadModeValue:
        return cast(ReadModeValue, _read_mode_cache.get(self._session, "READ_MODE"))

    def create_order(
        self,
        customer_id: int,
        total_amount: Decimal,
        order_status: OrderStatus,
        billing_email: str | None,
    ) -> Order:
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        write_mode = self._write_mode()

        # legacy: write billing_email only to orders (old column)
        # dual:   write to both orders.billing_email and order_contact_email
        # new:    write only to order_contact_email; orders.billing_email left NULL
        legacy_email = billing_email if write_mode in ("legacy", "dual") else None

        order_row = OrderModel(
            customer_id=customer_id,
            total_amount=total_amount,
            order_status=order_status,
            submitted_at=now,
            billing_email=legacy_email,
        )
        self._session.add(order_row)
        self._session.flush()

        if billing_email is not None and write_mode in ("dual", "new"):
            stmt = (
                pg_insert(OrderContactEmailModel)
                .values(
                    order_id=order_row.id,
                    billing_email=billing_email,
                    source="app",
                    updated_at=now,
                )
                .on_conflict_do_update(
                    index_elements=["order_id"],
                    set_={
                        "billing_email": billing_email,
                        "source": "app",
                        "updated_at": now,
                    },
                )
            )
            self._session.execute(stmt)

        self._session.commit()
        self._session.refresh(order_row)

        # Return billing_email consistent with what get_order would return —
        # i.e. from the source that READ_MODE designates, not the raw input.
        # This avoids a latent inconsistency where create_order returns the
        # input value while get_order returns NULL (e.g. WRITE_MODE=new stores
        # NULL in orders.billing_email but the input email is in the new table).
        read_mode = self._read_mode()
        if read_mode == "legacy":
            returned_email = order_row.billing_email
        else:
            contact = self._session.get(OrderContactEmailModel, order_row.id)
            returned_email = contact.billing_email if contact else None

        return Order(
            id=order_row.id,
            customer_id=order_row.customer_id,
            total_amount=order_row.total_amount,
            order_status=order_row.order_status,
            submitted_at=order_row.submitted_at,
            created_at=order_row.created_at,
            billing_email=returned_email,
        )

    def get_order(self, order_id: int) -> Order | None:
        order_row = self._session.get(OrderModel, order_id)
        if order_row is None:
            return None

        read_mode = self._read_mode()

        if read_mode == "legacy":
            billing_email = order_row.billing_email
        else:
            contact = self._session.get(OrderContactEmailModel, order_id)
            billing_email = contact.billing_email if contact else None

        return Order(
            id=order_row.id,
            customer_id=order_row.customer_id,
            total_amount=order_row.total_amount,
            order_status=order_row.order_status,
            submitted_at=order_row.submitted_at,
            created_at=order_row.created_at,
            billing_email=billing_email,
        )


class SQLAlchemyCustomerRepository(CustomerRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_customer(self, customer_id: int) -> Customer | None:
        row = self._session.get(CustomerModel, customer_id)
        if row is None:
            return None
        return Customer(id=row.id, name=row.name, created_at=row.created_at)
