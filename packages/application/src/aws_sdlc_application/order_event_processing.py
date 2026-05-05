import datetime
from typing import Any

from aws_sdlc_application.order_event_receipts import (
    OrderEventReceiptRepository,
    OrderEventReceiptResult,
)
from aws_sdlc_application.outbox import (
    OutboxDispatchResult,
    OutboxPublisher,
    OutboxRepository,
    dispatch_pending_outbox_messages,
)


def relay_order_outbox_once(
    *,
    outbox: OutboxRepository,
    publisher: OutboxPublisher,
    limit: int,
) -> OutboxDispatchResult:
    return dispatch_pending_outbox_messages(
        outbox=outbox,
        publisher=publisher,
        limit=limit,
    )


def record_order_event_receipt(
    *,
    receipts: OrderEventReceiptRepository,
    payload: dict[str, Any],
    now: datetime.datetime | None = None,
) -> OrderEventReceiptResult:
    return receipts.record(payload, now=now or datetime.datetime.now(tz=datetime.UTC))
