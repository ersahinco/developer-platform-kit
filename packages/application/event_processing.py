import datetime
from collections.abc import Callable
from typing import Any

from application.event_receipts import (
    EventReceiptRepository,
    EventReceiptResult,
)
from application.outbox import (
    OutboxDispatchResult,
    OutboxPublisher,
    OutboxRepository,
    dispatch_pending_outbox_messages,
)


def run_event_relay(
    *,
    outbox: OutboxRepository,
    publisher: OutboxPublisher,
    limit: int,
    stop_requested: Callable[[], bool],
    wait_for_retry: Callable[[float], object],
    idle_sleep_seconds: float,
    run_once: bool,
    on_result: Callable[[OutboxDispatchResult], None] | None = None,
) -> None:
    while not stop_requested():
        result = dispatch_pending_outbox_messages(
            outbox=outbox,
            publisher=publisher,
            limit=limit,
        )
        if on_result is not None:
            on_result(result)
        if run_once:
            return
        if result.published == 0 and result.failed == 0:
            wait_for_retry(idle_sleep_seconds)


def record_event_receipt(
    *,
    receipts: EventReceiptRepository,
    payload: dict[str, Any],
    now: datetime.datetime | None = None,
) -> EventReceiptResult:
    return receipts.record(payload, now=now or datetime.datetime.now(tz=datetime.UTC))
