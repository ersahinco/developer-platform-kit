import datetime
import threading
import time
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from infrastructure.db.models import (
    AppRuntimeConfigModel,
    CustomerModel,
    IdempotencyKeyModel,
    OutboxMessageModel,
    OrderEventReceiptModel,
    OrderContactEmailModel,
    OrderModel,
)
from domain.customer import Customer
from application.idempotency import IdempotencyBeginResult
from application.observability import ObservabilityFixtureRepository
from domain.order import Order, ReadModeValue, WriteModeValue
from application.order_event_receipts import OrderEventReceiptResult
from domain.order_events import OrderEventMessage, order_created_message
from application.outbox import OutboxMessage
from application.ports import ConfigStore, CustomerRepository, OrderRepository

_TTL_SECONDS = 5  # re-read app_runtime_config at most every 5 seconds
_IDEMPOTENCY_PROCESSING_SECONDS = 60


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
            order_status="SUBMITTED",
            submitted_at=now,
            created_at=now,
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

        order = Order(
            id=order_row.id,
            customer_id=order_row.customer_id,
            total_amount=order_row.total_amount,
            order_status=order_row.order_status,
            submitted_at=order_row.submitted_at,
            created_at=order_row.created_at,
            billing_email=billing_email,
        )
        SQLAlchemyOutboxRepository(self._session).enqueue(order_created_message(order))

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


class SQLAlchemyObservabilityFixtureRepository(ObservabilityFixtureRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure_customer(self, *, name: str) -> Customer:
        row = (
            self._session.execute(
                select(CustomerModel)
                .where(CustomerModel.name == name)
                .order_by(CustomerModel.id)
                .limit(1)
            )
            .scalars()
            .first()
        )
        if row is None:
            row = CustomerModel(name=name)
            self._session.add(row)
            self._session.commit()
            self._session.refresh(row)

        return Customer(id=row.id, name=row.name, created_at=row.created_at)


class SQLAlchemyOutboxRepository:
    _LOCK_SECONDS = 300

    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(self, message: OrderEventMessage) -> None:
        now = datetime.datetime.now(tz=datetime.UTC)
        stmt = (
            pg_insert(OutboxMessageModel)
            .values(
                event_type=message.event_type,
                event_id=message.event_id,
                aggregate_type=message.aggregate_type,
                aggregate_id=message.aggregate_id,
                message_group_id=message.message_group_id,
                message_deduplication_id=message.message_deduplication_id,
                payload=message.payload,
                status="pending",
                attempt_count=0,
                next_attempt_at=now,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["event_id"])
        )
        self._session.execute(stmt)

    def claim_pending(
        self,
        *,
        limit: int,
        now: datetime.datetime,
    ) -> list[OutboxMessage]:
        locked_until = now + datetime.timedelta(seconds=self._LOCK_SECONDS)
        stmt = (
            select(OutboxMessageModel)
            .where(
                OutboxMessageModel.next_attempt_at <= now,
                or_(
                    OutboxMessageModel.status == "pending",
                    (
                        (OutboxMessageModel.status == "processing")
                        & (OutboxMessageModel.locked_until <= now)
                    ),
                ),
            )
            .order_by(OutboxMessageModel.created_at, OutboxMessageModel.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = list(self._session.execute(stmt).scalars())
        for row in rows:
            row.status = "processing"
            row.locked_until = locked_until
            row.attempt_count += 1
            row.updated_at = now
        self._session.commit()
        return [_to_outbox_message(row) for row in rows]

    def mark_published(
        self,
        *,
        message_id: int,
        now: datetime.datetime,
    ) -> None:
        row = self._session.get(OutboxMessageModel, message_id)
        if row is None:
            return
        row.status = "published"
        row.published_at = now
        row.locked_until = None
        row.last_error = None
        row.updated_at = now
        self._session.commit()

    def mark_failed(
        self,
        *,
        message_id: int,
        error: str,
        next_attempt_at: datetime.datetime,
        now: datetime.datetime,
    ) -> None:
        row = self._session.get(OutboxMessageModel, message_id)
        if row is None:
            return
        row.status = "pending"
        row.locked_until = None
        row.last_error = error[:2000]
        row.next_attempt_at = next_attempt_at
        row.updated_at = now
        self._session.commit()


def _to_outbox_message(row: OutboxMessageModel) -> OutboxMessage:
    return OutboxMessage(
        id=row.id,
        event_type=row.event_type,
        event_id=row.event_id,
        aggregate_type=row.aggregate_type,
        aggregate_id=row.aggregate_id,
        message_group_id=row.message_group_id,
        message_deduplication_id=row.message_deduplication_id,
        payload=row.payload,
        attempt_count=row.attempt_count,
    )


class SQLAlchemyIdempotencyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def begin(self, *, key: str, request_hash: str) -> IdempotencyBeginResult:
        now = datetime.datetime.now(tz=datetime.UTC)
        processing_expires_at = now + datetime.timedelta(
            seconds=_IDEMPOTENCY_PROCESSING_SECONDS
        )
        result = self._session.execute(
            pg_insert(IdempotencyKeyModel)
            .values(
                key=key,
                request_hash=request_hash,
                status="processing",
                processing_expires_at=processing_expires_at,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["key"])
        )
        self._session.commit()
        if cast(Any, result).rowcount == 1:
            return IdempotencyBeginResult(status="started")

        row = self._session.get(IdempotencyKeyModel, key)
        if row is None:
            return IdempotencyBeginResult(status="processing")
        if row.request_hash != request_hash:
            return IdempotencyBeginResult(status="conflict")
        if row.status == "completed":
            return IdempotencyBeginResult(
                status="replay",
                response_status_code=row.response_status_code,
                response_payload=row.response_payload,
            )
        if row.processing_expires_at <= now:
            row.status = "processing"
            row.response_status_code = None
            row.response_payload = None
            row.processing_expires_at = processing_expires_at
            row.last_error = None
            row.updated_at = now
            self._session.commit()
            return IdempotencyBeginResult(status="started")
        return IdempotencyBeginResult(status="processing")

    def complete(
        self,
        *,
        key: str,
        response_status_code: int,
        response_payload: dict[str, object],
    ) -> None:
        row = self._session.get(IdempotencyKeyModel, key)
        if row is None:
            return
        now = datetime.datetime.now(tz=datetime.UTC)
        row.status = "completed"
        row.response_status_code = response_status_code
        row.response_payload = response_payload
        row.last_error = None
        row.updated_at = now
        self._session.commit()

    def fail(self, *, key: str, error: str) -> None:
        row = self._session.get(IdempotencyKeyModel, key)
        if row is None:
            return
        now = datetime.datetime.now(tz=datetime.UTC)
        row.status = "failed"
        row.last_error = error[:2000]
        row.updated_at = now
        self._session.commit()


class SQLAlchemyOrderEventReceiptRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        payload: dict[str, object],
        *,
        now: datetime.datetime,
    ) -> OrderEventReceiptResult:
        event_id = _required_str(payload, "event_id")
        event_type = _required_str(payload, "event_type")
        idempotency_key = _required_str(payload, "idempotency_key")
        occurred_at = _parse_event_time(_required_str(payload, "occurred_at"))
        order_payload = payload.get("order")
        if not isinstance(order_payload, dict):
            raise ValueError("order event payload must include an order object")
        aggregate_id = int(order_payload["id"])

        existing = self._session.get(OrderEventReceiptModel, event_id)
        if existing is not None:
            existing.duplicate_count += 1
            existing.last_seen_at = now
            self._session.commit()
            return OrderEventReceiptResult(status="duplicate", event_id=event_id)

        later_processed = self._session.execute(
            select(OrderEventReceiptModel.event_id)
            .where(
                OrderEventReceiptModel.event_type == event_type,
                OrderEventReceiptModel.aggregate_type == "order",
                OrderEventReceiptModel.aggregate_id == aggregate_id,
                OrderEventReceiptModel.status == "processed",
                OrderEventReceiptModel.occurred_at > occurred_at,
            )
            .limit(1)
        ).scalar_one_or_none()
        receipt_status = "ignored_stale" if later_processed else "processed"

        self._session.add(
            OrderEventReceiptModel(
                event_id=event_id,
                event_type=event_type,
                aggregate_type="order",
                aggregate_id=aggregate_id,
                idempotency_key=idempotency_key,
                occurred_at=occurred_at,
                payload=payload,
                status=receipt_status,
                duplicate_count=0,
                first_seen_at=now,
                last_seen_at=now,
            )
        )
        self._session.commit()
        return OrderEventReceiptResult(
            status="ignored_stale"
            if receipt_status == "ignored_stale"
            else "processed",
            event_id=event_id,
        )


def _required_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"order event payload must include {key}")
    return value


def _parse_event_time(value: str) -> datetime.datetime:
    parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.UTC)
    return parsed.astimezone(datetime.UTC)
