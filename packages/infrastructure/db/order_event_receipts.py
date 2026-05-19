import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from application.order_event_receipts import OrderEventReceiptResult
from infrastructure.db.models import OrderEventReceiptModel


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
