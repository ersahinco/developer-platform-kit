from __future__ import annotations

import datetime
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "core" / "src"))

from aws_sdlc_api.events import SqsOrderEventPublisher  # noqa: E402
from aws_sdlc_core.order import Order  # noqa: E402
from aws_sdlc_core.order_events import order_created_event, order_created_message  # noqa: E402


class _SqsClient:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def send_message(
        self,
        *,
        QueueUrl: str,
        MessageBody: str,
        MessageGroupId: str,
        MessageDeduplicationId: str,
    ) -> object:
        self.messages.append(
            {
                "QueueUrl": QueueUrl,
                "MessageBody": MessageBody,
                "MessageGroupId": MessageGroupId,
                "MessageDeduplicationId": MessageDeduplicationId,
            }
        )
        return {"MessageId": "message-1"}


def _order() -> Order:
    now = datetime.datetime(2026, 4, 29, 12, 30, tzinfo=datetime.UTC)
    return Order(
        id=42,
        customer_id=7,
        total_amount=Decimal("19.99"),
        order_status="SUBMITTED",
        submitted_at=now,
        created_at=now,
    )


def test_order_created_event_has_stable_idempotency_key() -> None:
    event = order_created_event(_order())

    assert event["event_type"] == "order.created.v1"
    assert event["event_version"] == 1
    assert event["event_id"] == "order.created.v1:42"
    assert event["idempotency_key"] == "order.created.v1:42"
    assert event["occurred_at"] == "2026-04-29T12:30:00Z"
    assert event["order"] == {
        "id": 42,
        "customer_id": 7,
        "total_amount": "19.99",
        "status": "SUBMITTED",
        "submitted_at": "2026-04-29T12:30:00Z",
        "created_at": "2026-04-29T12:30:00Z",
    }


def test_order_created_message_carries_fifo_metadata() -> None:
    message = order_created_message(_order())

    assert message.event_type == "order.created.v1"
    assert message.event_id == "order.created.v1:42"
    assert message.aggregate_type == "order"
    assert message.aggregate_id == 42
    assert message.message_group_id == "customer-7"
    assert message.message_deduplication_id == "order.created.v1:42"


def test_sqs_publisher_uses_fifo_group_and_deduplication_id() -> None:
    client = _SqsClient()
    publisher = SqsOrderEventPublisher(
        "https://sqs.eu-central-1.amazonaws.com/123/order-events.fifo",
        client=client,
    )

    publisher.publish_order_created(_order())

    assert len(client.messages) == 1
    message = client.messages[0]
    assert message["MessageGroupId"] == "customer-7"
    assert message["MessageDeduplicationId"] == "order.created.v1:42"
    assert json.loads(message["MessageBody"])["event_id"] == "order.created.v1:42"
