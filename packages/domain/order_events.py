import datetime
from dataclasses import dataclass
from typing import Any

from domain.order import Order

ORDER_CREATED_EVENT_TYPE = "order.created.v1"


@dataclass(frozen=True)
class OrderEventMessage:
    event_type: str
    event_id: str
    aggregate_type: str
    aggregate_id: int
    message_group_id: str
    message_deduplication_id: str
    payload: dict[str, Any]


def order_created_event(order: Order) -> dict[str, Any]:
    occurred_at = _isoformat(order.created_at)
    return {
        "event_type": ORDER_CREATED_EVENT_TYPE,
        "event_version": 1,
        "event_id": f"{ORDER_CREATED_EVENT_TYPE}:{order.id}",
        "idempotency_key": f"{ORDER_CREATED_EVENT_TYPE}:{order.id}",
        "occurred_at": occurred_at,
        "order": {
            "id": order.id,
            "customer_id": order.customer_id,
            "total_amount": str(order.total_amount),
            "status": order.order_status,
            "submitted_at": _isoformat(order.submitted_at),
            "created_at": occurred_at,
        },
    }


def order_created_message(order: Order) -> OrderEventMessage:
    payload = order_created_event(order)
    event_id = str(payload["event_id"])
    return OrderEventMessage(
        event_type=ORDER_CREATED_EVENT_TYPE,
        event_id=event_id,
        aggregate_type="order",
        aggregate_id=order.id,
        message_group_id=f"customer-{order.customer_id}",
        message_deduplication_id=event_id,
        payload=payload,
    )


def _isoformat(value: datetime.datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.UTC)
    return value.astimezone(datetime.UTC).isoformat().replace("+00:00", "Z")
